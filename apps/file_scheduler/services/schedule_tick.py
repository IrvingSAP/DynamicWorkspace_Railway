"""M4: worker de ticks — una ventana por plan, sin avalancha ni archivo inventado."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.dms.file_intake.models import DmsExecutionJob
from apps.file_clean.models import CleanJob
from apps.file_pipeline.models import PipelineDefinition, PipelineRun
from apps.file_scheduler.models import Schedule, ScheduleAuditEvent, ScheduleTick
from apps.file_scheduler.services import schedule_cron as cron_svc
from apps.file_scheduler.services import schedule_errors as err
from apps.file_scheduler.services import schedule_runner as runner_svc
from apps.file_scheduler.services import schedule_target as target_svc
from apps.accounts.models import UserProfile

logger = logging.getLogger(__name__)

TRIGGERED_BY = "system:scheduler"
MISFIRE_GRACE = timedelta(minutes=15)
LIVE_JOB = {
    DmsExecutionJob.STATUS_QUEUED,
    DmsExecutionJob.STATUS_RUNNING,
    DmsExecutionJob.STATUS_UPLOADED,
}
LIVE_CLEAN = {CleanJob.STATUS_QUEUED, CleanJob.STATUS_RUNNING}
LIVE_PIPELINE = {PipelineRun.STATUS_QUEUED, PipelineRun.STATUS_RUNNING}

MSG_PAUSED = err.MSG_PAUSED
MSG_MISFIRE = err.MSG_MISFIRE
MSG_ENQUEUE_FAILED = err.MSG_ENQUEUE_FAILED
MSG_MISSING_INPUT = err.MSG_MISSING_INPUT
MSG_NO_PUBLISHED = err.MSG_NO_PUBLISHED
MSG_OVERLAP = err.MSG_OVERLAP
MSG_WATCH_UNRESOLVED = MSG_MISSING_INPUT
MSG_ARTIFACT_NOT_FOUND = err.MSG_ARTIFACT_NOT_FOUND
MSG_RUNNER_UNSUPPORTED = err.MSG_RUNNER_UNSUPPORTED

STATUS_LABELS = {
    ScheduleTick.STATUS_ENQUEUED: "Encolado",
    ScheduleTick.STATUS_SKIPPED: "Omitido",
    ScheduleTick.STATUS_FAILED: "Falló",
    "running": "En curso",
}
DELEGATED_STATUS_LABELS = {
    DmsExecutionJob.STATUS_QUEUED: "En cola",
    DmsExecutionJob.STATUS_RUNNING: "En ejecución",
    DmsExecutionJob.STATUS_UPLOADED: "Subido",
    DmsExecutionJob.STATUS_COMPLETED: "Completado",
    DmsExecutionJob.STATUS_PARTIAL: "Parcial",
    DmsExecutionJob.STATUS_FAILED: "Fallido",
    DmsExecutionJob.STATUS_CANCELLED: "Cancelado",
    CleanJob.STATUS_QUEUED: "En cola",
    CleanJob.STATUS_RUNNING: "En ejecución",
    CleanJob.STATUS_COMPLETED: "Completado",
    CleanJob.STATUS_FAILED: "Fallido",
    PipelineRun.STATUS_QUEUED: "En cola",
    PipelineRun.STATUS_RUNNING: "En ejecución",
    PipelineRun.STATUS_COMPLETED: "Completado",
    PipelineRun.STATUS_FAILED: "Fallido",
    PipelineRun.STATUS_CANCELLED: "Cancelado",
}
KIND_APP_LABELS = {row["kind"]: row["label"] for row in target_svc.JOB_KINDS}
KIND_APP_LABELS["pipeline"] = "File Pipeline"


def _claim_watch_upload(schedule: Schedule):
    """
    Claim lote pending de File Watch.
    Retorna (upload, error) donde error es None | 'missing' | 'not_found'.
    """
    from apps.file_watch.services.watch_claim import (
        claim_pending_batch,
        get_watch_by_slug,
    )

    watch_slug = (schedule.watch_id or "").strip()
    if not watch_slug:
        return None, "missing"
    watch = get_watch_by_slug(schedule.company, watch_slug)
    pick = watch.pending_pick_policy if watch is not None else None
    batch = claim_pending_batch(
        schedule.company,
        watch_slug,
        pick_policy=pick,
        schedule_slug=schedule.slug,
    )
    if batch is None:
        return None, "missing"
    upload = runner_svc.wrap_stored_upload(
        batch.storage_key, batch.original_filename or "file"
    )
    if upload is None:
        # También intentar por hash vía resolve_artifact (Jobs previos / WatchBatch)
        resolved = runner_svc.resolve_artifact(schedule.company_id, batch.content_hash)
        if resolved:
            upload = runner_svc.wrap_stored_upload(
                resolved["stored_path"], resolved.get("filename") or batch.original_filename
            )
    if upload is None:
        return None, "not_found"
    return upload, None


def last_tick_label(schedule: Schedule) -> str:
    tick = (
        ScheduleTick.objects.filter(schedule=schedule)
        .order_by("-scheduled_for")
        .first()
    )
    if tick is None:
        return "—"
    local = timezone.localtime(tick.scheduled_for)
    return local.strftime("%Y-%m-%d %H:%M")


def list_ticks(schedule: Schedule):
    return list(
        ScheduleTick.objects.filter(schedule=schedule)
        .select_related(
            "schedule",
            "schedule__target_project",
            "schedule__target_pipeline",
        )
        .order_by("-scheduled_for")
    )


def tick_ui_status(tick: ScheduleTick) -> str:
    if tick.status == ScheduleTick.STATUS_ENQUEUED and _delegated_is_live(tick):
        return "running"
    return tick.status


def tick_row(tick: ScheduleTick, user=None) -> dict:
    ui = tick_ui_status(tick)
    snap = _delegated_snapshot(tick, user=user)
    return {
        "tick": tick,
        "scheduled_for": tick.scheduled_for,
        "status": ui,
        "status_label": STATUS_LABELS.get(ui, ui),
        "error_code": tick.error_code,
        "user_message": _activity_message(tick, ui, snap, user=user),
        "correlation_id": tick.correlation_id,
        "job_id": tick.job_id,
        "pipeline_run_id": tick.pipeline_run_id,
        "run_kind": "pipeline" if tick.pipeline_run_id else ("job" if tick.job_id else ""),
        "run_href": snap.get("run_href") or "",
        "run_label": snap.get("run_label") or "",
        "run_blocked_reason": snap.get("run_blocked_reason") or "",
        "delegated_status": snap.get("delegated_status") or "",
        "delegated_status_label": snap.get("delegated_status_label") or "",
        "app_label": snap.get("app_label") or "",
    }


def process_due_ticks(*, now: datetime | None = None) -> dict:
    moment = now or timezone.now()
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, timezone.get_current_timezone())
    processed = 0
    qs = (
        Schedule.objects.filter(
            status=Schedule.STATUS_ACTIVE,
            company__is_active=True,
        )
        .exclude(trigger_mode=Schedule.TRIGGER_DEPENDENCY)
        .select_related(
            "company",
            "target_project",
            "target_project__dms_config",
            "target_project__dms_config__current_version",
            "target_pipeline",
            "target_pipeline__current_version",
        )
        .order_by("pk")
    )
    for schedule in qs:
        result = process_schedule_slot(schedule, now=moment)
        if result:
            processed += 1
    return {"processed": processed}


def process_schedule_slot(schedule: Schedule, *, now: datetime) -> ScheduleTick | None:
    if schedule.status != Schedule.STATUS_ACTIVE:
        return None
    if schedule.trigger_mode == Schedule.TRIGGER_DEPENDENCY:
        return None
    if not schedule.programming_complete or not schedule.target_complete:
        return None
    slot = cron_svc.latest_due_slot(schedule, now)
    if slot is None:
        return None
    slot_utc = slot.astimezone(timezone.UTC)
    if ScheduleTick.objects.filter(schedule=schedule, scheduled_for=slot_utc).exists():
        return None

    if now - slot_utc > MISFIRE_GRACE:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_SKIPPED,
            error_code="schedule_misfire",
            user_message=MSG_MISFIRE,
            event=ScheduleAuditEvent.EVENT_TICK_SKIPPED,
        )

    live = _live_previous_tick(schedule)
    policy = schedule.overlap_policy or Schedule.OVERLAP_SKIP
    if live is not None:
        if policy == Schedule.OVERLAP_SKIP:
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_SKIPPED,
                error_code="schedule_overlap_skip",
                user_message=MSG_OVERLAP,
                event=ScheduleAuditEvent.EVENT_TICK_SKIPPED,
                extra={"overlap_policy": policy},
            )
        if policy == Schedule.OVERLAP_CANCEL:
            _cancel_delegated(live)

    return _fire_slot(schedule, slot_utc)


def fire_from_parent(
    schedule: Schedule,
    *,
    now: datetime,
    parent_job_id: str = "",
    parent_pipeline_run_id: str = "",
) -> ScheduleTick | None:
    """Encola por dependencia. No usa misfire ni ventanas cron."""
    parent_job_id = (parent_job_id or "").strip()
    parent_pipeline_run_id = (parent_pipeline_run_id or "").strip()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    slot_utc = now.astimezone(timezone.UTC)

    exists = ScheduleTick.objects.filter(schedule=schedule)
    if parent_job_id:
        exists = exists.filter(parent_job_id=parent_job_id)
    elif parent_pipeline_run_id:
        exists = exists.filter(parent_pipeline_run_id=parent_pipeline_run_id)
    else:
        return None
    if exists.exists():
        return None

    extra = {
        "trigger_source": "dependency",
        "parent_job_id": parent_job_id,
        "parent_pipeline_run_id": parent_pipeline_run_id,
    }
    if schedule.status != Schedule.STATUS_ACTIVE:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_SKIPPED,
            error_code="schedule_paused",
            user_message=MSG_PAUSED,
            event=ScheduleAuditEvent.EVENT_TICK_SKIPPED,
            parent_job_id=parent_job_id,
            parent_pipeline_run_id=parent_pipeline_run_id,
            extra=extra,
        )
    if not schedule.target_complete:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_no_published_target",
            user_message=MSG_NO_PUBLISHED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            parent_job_id=parent_job_id,
            parent_pipeline_run_id=parent_pipeline_run_id,
            extra=extra,
        )

    live = _live_previous_tick(schedule)
    policy = schedule.overlap_policy or Schedule.OVERLAP_SKIP
    if live is not None:
        if policy == Schedule.OVERLAP_SKIP:
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_SKIPPED,
                error_code="schedule_overlap_skip",
                user_message=MSG_OVERLAP,
                event=ScheduleAuditEvent.EVENT_TICK_SKIPPED,
                parent_job_id=parent_job_id,
                parent_pipeline_run_id=parent_pipeline_run_id,
                extra={**extra, "overlap_policy": policy},
            )
        if policy == Schedule.OVERLAP_CANCEL:
            _cancel_delegated(live)

    return _fire_slot(
        schedule,
        slot_utc,
        trigger_source="dependency",
        parent_job_id=parent_job_id,
        parent_pipeline_run_id=parent_pipeline_run_id,
    )


def _live_previous_tick(schedule: Schedule) -> ScheduleTick | None:
    previous = (
        ScheduleTick.objects.filter(
            schedule=schedule, status=ScheduleTick.STATUS_ENQUEUED
        )
        .order_by("-scheduled_for")
        .first()
    )
    if previous is None:
        return None
    if _delegated_is_live(previous):
        return previous
    return None


def _cancel_delegated(tick: ScheduleTick) -> None:
    now = timezone.now()
    if tick.pipeline_run_id:
        run = PipelineRun.objects.filter(pk=tick.pipeline_run_id).first()
        if run is not None and run.status in LIVE_PIPELINE:
            run.status = PipelineRun.STATUS_CANCELLED
            run.finished_at = now
            run.error_message = "Cancelado por solape del Scheduler."
            run.save(update_fields=["status", "finished_at", "error_message"])
    if tick.job_id:
        job = DmsExecutionJob.objects.filter(pk=tick.job_id).first()
        if job is not None and job.status in LIVE_JOB:
            suggestions = dict(job.input_suggestions or {})
            suggestions["cancelled_by"] = TRIGGERED_BY
            suggestions["cancel_reason"] = "overlap_cancel_previous"
            job.status = DmsExecutionJob.STATUS_CANCELLED
            job.input_suggestions = suggestions
            job.finished_at = now
            job.save(
                update_fields=["status", "input_suggestions", "finished_at", "updated_at"]
            )
        clean = CleanJob.objects.filter(pk=tick.job_id).first()
        if clean is not None and clean.status in LIVE_CLEAN:
            clean.status = CleanJob.STATUS_FAILED
            clean.error_message = "Cancelado por solape del Scheduler."
            clean.error_code = "cancelled"
            clean.finished_at = now
            clean.save(
                update_fields=["status", "error_message", "error_code", "finished_at"]
            )


def _delegated_is_live(tick: ScheduleTick) -> bool:
    if tick.pipeline_run_id:
        run = PipelineRun.objects.filter(pk=tick.pipeline_run_id).first()
        return run is not None and run.status in LIVE_PIPELINE
    if not tick.job_id:
        return False
    clean = CleanJob.objects.filter(pk=tick.job_id).first()
    if clean is not None:
        return clean.status in LIVE_CLEAN
    job = DmsExecutionJob.objects.filter(pk=tick.job_id).first()
    return job is not None and job.status in LIVE_JOB


def _kind_for_tick(tick: ScheduleTick) -> str:
    payload = tick.payload or {}
    kind = str(payload.get("kind") or "").strip()
    if kind:
        return kind
    schedule = getattr(tick, "schedule", None)
    if schedule is None:
        return ""
    if schedule.target_mode == Schedule.TARGET_PIPELINE:
        return "pipeline"
    return (schedule.target_kind or "").strip()


def _project_slug_for_tick(tick: ScheduleTick) -> str:
    schedule = getattr(tick, "schedule", None)
    project = getattr(schedule, "target_project", None) if schedule else None
    if project is not None:
        return project.slug
    if tick.job_id:
        job = DmsExecutionJob.objects.filter(pk=tick.job_id).select_related("project").first()
        if job is not None:
            return job.project.slug
    return ""


def _run_href(kind: str, project_slug: str, job_id: str, pipeline_run_id: str) -> str:
    try:
        if pipeline_run_id:
            run = (
                PipelineRun.objects.filter(pk=pipeline_run_id)
                .select_related("pipeline")
                .first()
            )
            if run is None:
                return ""
            return reverse(
                "file_pipeline:pipeline_run_result",
                kwargs={"pipeline_slug": run.pipeline.slug, "run_id": run.id},
            )
        if not job_id or not project_slug:
            return ""
        if kind == "file_gate":
            return reverse(
                "file_gate:run_result",
                kwargs={"project_slug": project_slug, "job_id": job_id},
            )
        if kind == "file_clean":
            return reverse(
                "file_clean:history_detail",
                kwargs={"project_slug": project_slug, "job_id": job_id},
            )
        if kind in {"file_split", "file_merge"}:
            return reverse(
                "file_split_merge:history_hub", kwargs={"project_slug": project_slug}
            )
        if kind == "file_match":
            return reverse("file_match:history_hub", kwargs={"project_slug": project_slug})
        if kind == "dms":
            return reverse(
                "dms:transform_execution_history",
                kwargs={"project_slug": project_slug},
            )
        if kind == "reverse":
            return reverse("reverse_studio:history_hub", kwargs={"project_slug": project_slug})
    except Exception:
        logger.exception("tick run href failed kind=%s job=%s", kind, job_id)
        return ""
    return ""


def _user_is_uf(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    try:
        return user.profile.user_type == UserProfile.USER_FINAL
    except Exception:
        return False


def _delegated_snapshot(tick: ScheduleTick, user=None) -> dict:
    kind = _kind_for_tick(tick)
    app_label = KIND_APP_LABELS.get(kind, kind or "app destino")
    can_open = _user_is_uf(user)
    blocked = (
        ""
        if can_open
        else "El historial de la app destino solo lo abre un usuario UF (miembro del proyecto)."
    )

    if tick.pipeline_run_id:
        run = (
            PipelineRun.objects.filter(pk=tick.pipeline_run_id)
            .select_related("pipeline")
            .first()
        )
        if run is None:
            return {"app_label": "File Pipeline", "run_blocked_reason": blocked}
        return {
            "app_label": "File Pipeline",
            "delegated_status": run.status,
            "delegated_status_label": DELEGATED_STATUS_LABELS.get(run.status, run.status),
            "run_href": _run_href("pipeline", "", "", str(run.id)) if can_open else "",
            "run_label": f"pipeline {str(run.id)[:8]}",
            "run_blocked_reason": blocked,
        }
    if tick.job_id:
        clean = CleanJob.objects.filter(pk=tick.job_id).select_related("project").first()
        if clean is not None:
            slug = clean.project.slug
            if can_open:
                if clean.status in LIVE_CLEAN:
                    href = reverse(
                        "file_clean:history_hub", kwargs={"project_slug": slug}
                    )
                else:
                    href = _run_href("file_clean", slug, str(clean.id), "")
            else:
                href = ""
            return {
                "app_label": app_label or "File Clean",
                "delegated_status": clean.status,
                "delegated_status_label": DELEGATED_STATUS_LABELS.get(
                    clean.status, clean.status
                ),
                "run_href": href,
                "run_label": f"job {str(clean.id)[:8]}",
                "run_blocked_reason": blocked,
            }
        job = (
            DmsExecutionJob.objects.filter(pk=tick.job_id).select_related("project").first()
        )
        slug = job.project.slug if job is not None else _project_slug_for_tick(tick)
        status = job.status if job is not None else ""
        href_kind = kind or "file_gate"
        return {
            "app_label": app_label,
            "delegated_status": status,
            "delegated_status_label": DELEGATED_STATUS_LABELS.get(status, status),
            "run_href": _run_href(href_kind, slug, str(tick.job_id), "") if can_open else "",
            "run_label": f"job {str(tick.job_id)[:8]}",
            "run_blocked_reason": blocked,
        }
    return {}


def _activity_message(tick: ScheduleTick, ui: str, snap: dict, user=None) -> str:
    if tick.user_message:
        return tick.user_message
    catalog = err.message_for(tick.error_code)
    if catalog:
        return catalog
    app = snap.get("app_label") or "la app destino"
    status = snap.get("delegated_status") or ""
    if ui == "running" or status in LIVE_JOB or status in LIVE_PIPELINE:
        if status in {
            DmsExecutionJob.STATUS_QUEUED,
            DmsExecutionJob.STATUS_UPLOADED,
            PipelineRun.STATUS_QUEUED,
        }:
            base = (
                f"Encolado en {app}; el Job sigue en cola. "
                f"El Scheduler no ejecuta la app: el log está en el historial de {app}."
            )
        else:
            base = f"En ejecución en {app}. El detalle y el log están en esa app, no aquí."
        if snap.get("run_blocked_reason") and not _user_is_uf(user):
            return f"{base} Abra esa pantalla con un usuario UF del proyecto."
        return base
    if ui == ScheduleTick.STATUS_ENQUEUED:
        label = snap.get("delegated_status_label") or "terminó"
        base = f"Encolado. {app} {label.lower()}. Abra el historial de {app} para el log."
        if snap.get("run_blocked_reason") and not _user_is_uf(user):
            return f"{base} Use un usuario UF del proyecto."
        return base
    return ""


def _fire_slot(
    schedule: Schedule,
    slot_utc: datetime,
    *,
    trigger_source: str = "scheduler",
    parent_job_id: str = "",
    parent_pipeline_run_id: str = "",
) -> ScheduleTick | None:
    correlation = uuid.uuid4().hex
    try:
        if schedule.target_mode == Schedule.TARGET_PIPELINE:
            return _enqueue_pipeline(
                schedule,
                slot_utc,
                correlation,
                trigger_source=trigger_source,
                parent_job_id=parent_job_id,
                parent_pipeline_run_id=parent_pipeline_run_id,
            )
        return _enqueue_job(
            schedule,
            slot_utc,
            correlation,
            trigger_source=trigger_source,
            parent_job_id=parent_job_id,
            parent_pipeline_run_id=parent_pipeline_run_id,
        )
    except Exception:
        logger.exception("schedule tick enqueue id=%s", schedule.pk)
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_enqueue_failed",
            user_message=MSG_ENQUEUE_FAILED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            parent_job_id=parent_job_id,
            parent_pipeline_run_id=parent_pipeline_run_id,
        )


def _enqueue_job(
    schedule: Schedule,
    slot_utc: datetime,
    correlation: str,
    *,
    trigger_source: str = "scheduler",
    parent_job_id: str = "",
    parent_pipeline_run_id: str = "",
) -> ScheduleTick:
    parent = {
        "parent_job_id": parent_job_id,
        "parent_pipeline_run_id": parent_pipeline_run_id,
    }
    extra_src = {"trigger_source": trigger_source, **parent}
    project = schedule.target_project
    if project is None or project.company_id != schedule.company_id:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_no_published_target",
            user_message=MSG_NO_PUBLISHED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    version_number = target_svc.published_version_number(project)
    if version_number is None:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_no_published_target",
            user_message=MSG_NO_PUBLISHED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    if schedule.input_origin == Schedule.INPUT_NONE:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_missing_input",
            user_message=MSG_MISSING_INPUT,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    config = getattr(project, "dms_config", None)
    version = getattr(config, "current_version", None) if config else None
    if version is None:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_no_published_target",
            user_message=MSG_NO_PUBLISHED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    upload = None
    if schedule.input_origin == Schedule.INPUT_WATCH:
        upload, watch_err = _claim_watch_upload(schedule)
        if watch_err == "missing":
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_FAILED,
                error_code="schedule_missing_input",
                user_message=MSG_WATCH_UNRESOLVED,
                event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                correlation_id=correlation,
                extra=extra_src,
                **parent,
            )
        if watch_err == "not_found" or upload is None:
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_FAILED,
                error_code="schedule_artifact_not_found",
                user_message=MSG_ARTIFACT_NOT_FOUND,
                event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                correlation_id=correlation,
                extra=extra_src,
                **parent,
            )
    else:
        artifact = (schedule.artifact_ref or "").strip()
        if schedule.input_origin == Schedule.INPUT_ARTIFACT and not artifact:
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_FAILED,
                error_code="schedule_missing_input",
                user_message=MSG_MISSING_INPUT,
                event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                correlation_id=correlation,
                extra=extra_src,
                **parent,
            )
        resolved = runner_svc.resolve_artifact(schedule.company_id, artifact)
        upload = (
            runner_svc.wrap_stored_upload(
                resolved["stored_path"], resolved.get("filename") or ""
            )
            if resolved
            else None
        )
        if upload is None:
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_FAILED,
                error_code="schedule_artifact_not_found",
                user_message=MSG_ARTIFACT_NOT_FOUND,
                event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                correlation_id=correlation,
                extra=extra_src,
                **parent,
            )
    slot_iso = slot_utc.isoformat()
    result = runner_svc.run_job_kind(
        schedule,
        project,
        upload,
        trigger_source=trigger_source,
        correlation=correlation,
        slot_iso=slot_iso,
    )
    job = (result.payload or {}).get("job") if result.payload else None
    if job is not None:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_ENQUEUED,
            event=ScheduleAuditEvent.EVENT_TICK_ENQUEUED,
            correlation_id=correlation,
            job_id=str(job.id),
            extra={"kind": schedule.target_kind, "project_id": str(project.id), **extra_src},
            **parent,
        )
    code = result.error_code or "schedule_enqueue_failed"
    if code not in {
        "schedule_runner_unsupported",
        "schedule_artifact_not_found",
        "schedule_enqueue_failed",
        "schedule_missing_input",
        "schedule_no_published_target",
    }:
        code = "schedule_enqueue_failed"
    message = result.user_message or MSG_ENQUEUE_FAILED
    if code == "schedule_runner_unsupported":
        message = MSG_RUNNER_UNSUPPORTED
    return _persist_tick(
        schedule,
        slot_utc,
        status=ScheduleTick.STATUS_FAILED,
        error_code=code,
        user_message=message,
        event=ScheduleAuditEvent.EVENT_TICK_FAILED,
        correlation_id=correlation,
        extra=extra_src,
        **parent,
    )


def _enqueue_pipeline(
    schedule: Schedule,
    slot_utc: datetime,
    correlation: str,
    *,
    trigger_source: str = "scheduler",
    parent_job_id: str = "",
    parent_pipeline_run_id: str = "",
) -> ScheduleTick:
    parent = {
        "parent_job_id": parent_job_id,
        "parent_pipeline_run_id": parent_pipeline_run_id,
    }
    extra_src = {"trigger_source": trigger_source, **parent}
    ts = (
        PipelineRun.TRIGGER_DEPENDENCY
        if trigger_source == "dependency"
        else PipelineRun.TRIGGER_SCHEDULER
    )
    pipeline = schedule.target_pipeline
    if pipeline is None or pipeline.company_id != schedule.company_id:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_no_published_target",
            user_message=MSG_NO_PUBLISHED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    if (
        pipeline.current_version_id is None
        or pipeline.status != PipelineDefinition.STATUS_ACTIVE
    ):
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_no_published_target",
            user_message=MSG_NO_PUBLISHED,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    origin = schedule.input_origin
    if origin == Schedule.INPUT_NONE and not schedule.pipeline_inputs_resolved:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_missing_input",
            user_message=MSG_MISSING_INPUT,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    artifact = (schedule.artifact_ref or "").strip()
    if origin == Schedule.INPUT_ARTIFACT and not artifact:
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_FAILED,
            error_code="schedule_missing_input",
            user_message=MSG_MISSING_INPUT,
            event=ScheduleAuditEvent.EVENT_TICK_FAILED,
            correlation_id=correlation,
            extra=extra_src,
            **parent,
        )
    if origin in {Schedule.INPUT_ARTIFACT, Schedule.INPUT_WATCH}:
        from apps.file_pipeline.services import pipeline_run_service

        upload = None
        if origin == Schedule.INPUT_WATCH:
            upload, watch_err = _claim_watch_upload(schedule)
            if watch_err == "missing":
                return _persist_tick(
                    schedule,
                    slot_utc,
                    status=ScheduleTick.STATUS_FAILED,
                    error_code="schedule_missing_input",
                    user_message=MSG_WATCH_UNRESOLVED,
                    event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                    correlation_id=correlation,
                    extra=extra_src,
                    **parent,
                )
            if watch_err == "not_found" or upload is None:
                return _persist_tick(
                    schedule,
                    slot_utc,
                    status=ScheduleTick.STATUS_FAILED,
                    error_code="schedule_artifact_not_found",
                    user_message=MSG_ARTIFACT_NOT_FOUND,
                    event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                    correlation_id=correlation,
                    extra=extra_src,
                    **parent,
                )
        else:
            resolved = runner_svc.resolve_artifact(schedule.company_id, artifact)
            upload = (
                runner_svc.wrap_stored_upload(
                    resolved["stored_path"], resolved.get("filename") or ""
                )
                if resolved
                else None
            )
            if upload is None:
                return _persist_tick(
                    schedule,
                    slot_utc,
                    status=ScheduleTick.STATUS_FAILED,
                    error_code="schedule_artifact_not_found",
                    user_message=MSG_ARTIFACT_NOT_FOUND,
                    event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                    correlation_id=correlation,
                    extra=extra_src,
                    **parent,
                )
        result = pipeline_run_service.start_run(
            schedule.owner,
            pipeline,
            upload,
            dry_run=False,
            require_membership=False,
            trigger_source=ts,
            correlation_id=correlation,
        )
        run = (result.payload or {}).get("run") if result.payload else None
        if run is None:
            return _persist_tick(
                schedule,
                slot_utc,
                status=ScheduleTick.STATUS_FAILED,
                error_code="schedule_enqueue_failed",
                user_message=result.user_message or MSG_ENQUEUE_FAILED,
                event=ScheduleAuditEvent.EVENT_TICK_FAILED,
                correlation_id=correlation,
                extra=extra_src,
                **parent,
            )
        run.schedule_id = str(schedule.id)
        run.parent_job_id = parent_job_id[:36]
        run.parent_pipeline_run_id = parent_pipeline_run_id[:36]
        run.save(
            update_fields=["schedule_id", "parent_job_id", "parent_pipeline_run_id"]
        )
        return _persist_tick(
            schedule,
            slot_utc,
            status=ScheduleTick.STATUS_ENQUEUED,
            event=ScheduleAuditEvent.EVENT_TICK_ENQUEUED,
            correlation_id=correlation,
            pipeline_run_id=str(run.id),
            extra={"pipeline_id": str(pipeline.id), **extra_src},
            **parent,
        )
    run = PipelineRun.objects.create(
        pipeline=pipeline,
        version=pipeline.current_version,
        trigger_source=ts,
        status=PipelineRun.STATUS_QUEUED,
        input_sha256=artifact[:64],
        correlation_id=correlation[:64],
        schedule_id=str(schedule.id),
        parent_job_id=parent_job_id[:36],
        parent_pipeline_run_id=parent_pipeline_run_id[:36],
    )
    return _persist_tick(
        schedule,
        slot_utc,
        status=ScheduleTick.STATUS_ENQUEUED,
        event=ScheduleAuditEvent.EVENT_TICK_ENQUEUED,
        correlation_id=correlation,
        pipeline_run_id=str(run.id),
        extra={"pipeline_id": str(pipeline.id), **extra_src},
        **parent,
    )


def _persist_tick(
    schedule: Schedule,
    slot_utc: datetime,
    *,
    status: str,
    event: str,
    error_code: str = "",
    user_message: str = "",
    correlation_id: str = "",
    job_id: str = "",
    pipeline_run_id: str = "",
    parent_job_id: str = "",
    parent_pipeline_run_id: str = "",
    extra: dict | None = None,
) -> ScheduleTick | None:
    extra = extra or {}
    parent_job_id = parent_job_id or str(extra.get("parent_job_id") or "")
    parent_pipeline_run_id = parent_pipeline_run_id or str(
        extra.get("parent_pipeline_run_id") or ""
    )
    payload = {
        "triggered_by": TRIGGERED_BY,
        "scheduled_for": slot_utc.isoformat(),
        "company_id": str(schedule.company_id),
        "schedule_id": str(schedule.id),
        "correlation_id": correlation_id,
        "job_id": job_id,
        "pipeline_run_id": pipeline_run_id,
        "error_code": error_code,
        "cron_expr": schedule.cron_expr,
        "target_mode": schedule.target_mode,
        **(extra or {}),
    }
    try:
        with transaction.atomic():
            tick = ScheduleTick.objects.create(
                company=schedule.company,
                schedule=schedule,
                scheduled_for=slot_utc,
                status=status,
                error_code=error_code,
                user_message=user_message,
                correlation_id=correlation_id,
                job_id=job_id,
                pipeline_run_id=pipeline_run_id,
                parent_job_id=parent_job_id,
                parent_pipeline_run_id=parent_pipeline_run_id,
                payload=payload,
            )
            ScheduleAuditEvent.objects.create(
                company=schedule.company,
                schedule=schedule,
                event=event,
                actor=None,
                payload=payload,
            )
    except IntegrityError:
        return None
    except Exception:
        logger.exception("persist tick id=%s", schedule.pk)
        return None
    if tick is not None:
        transaction.on_commit(lambda t=tick: _notify_tick(t))
    return tick


def _notify_tick(tick: ScheduleTick) -> None:
    from apps.file_scheduler.services import schedule_notify as notify_svc

    try:
        notify_svc.dispatch_for_tick(tick)
    except Exception:
        logger.exception("notify tick id=%s", tick.pk)
