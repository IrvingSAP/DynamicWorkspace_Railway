"""M5: disparo on_arrival | pending_only."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.file_watch.models import Watch, WatchAuditEvent, WatchBatch
from apps.file_watch.services import watch_audit as audit_svc
from apps.file_watch.services import watch_errors as err
from apps.file_watch.services.watch_lifecycle_service import (
    MSG_FORBIDDEN,
    MSG_UNEXPECTED,
    MSG_VALIDATION,
    user_can_edit,
)

logger = logging.getLogger(__name__)

MSG_SAVED = "Disparo guardado correctamente."


def snapshot_from_watch(watch: Watch) -> dict:
    return {
        "fire_mode": watch.fire_mode or Watch.FIRE_PENDING_ONLY,
    }


def posted_from_request(post) -> dict:
    return {
        "fire_mode": (post.get("fire_mode") or "").strip(),
    }


def save_fire(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)

    mode = data.get("fire_mode") or ""
    errors: dict[str, list[str]] = {}
    if mode not in {Watch.FIRE_ON_ARRIVAL, Watch.FIRE_PENDING_ONLY}:
        errors.setdefault("fire_mode", []).append("Seleccione un modo de disparo.")

    if mode == Watch.FIRE_ON_ARRIVAL and watch.route_mode == Watch.ROUTE_DEFER:
        return OperationResult.failure(
            err.FIRE_ROUTE_CONFLICT,
            err.MESSAGES[err.FIRE_ROUTE_CONFLICT],
            errors={"fire_mode": [err.MESSAGES[err.FIRE_ROUTE_CONFLICT]]},
        )

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    try:
        with transaction.atomic():
            watch.fire_mode = mode
            watch.fire_saved_at = timezone.now()
            watch.save(update_fields=["fire_mode", "fire_saved_at", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_FIRE_UPDATED,
                user,
                {"fire_mode": mode},
            )
    except Exception:
        logger.exception("save_fire unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(user_message=MSG_SAVED, payload={"watch": watch})


def activation_checks(watch: Watch) -> OperationResult | None:
    """None si puede activar; OperationResult de fallo si no."""
    if not watch.source_complete:
        return OperationResult.failure(err.INCOMPLETE, err.MESSAGES[err.INCOMPLETE])
    if not watch.fire_complete:
        return OperationResult.failure(err.INCOMPLETE, err.MESSAGES[err.INCOMPLETE])
    if watch.fire_mode == Watch.FIRE_ON_ARRIVAL:
        if watch.route_mode == Watch.ROUTE_DEFER:
            return OperationResult.failure(
                err.FIRE_ROUTE_CONFLICT, err.MESSAGES[err.FIRE_ROUTE_CONFLICT]
            )
        if not watch.route_complete or watch.route_mode not in {
            Watch.ROUTE_JOB,
            Watch.ROUTE_PIPELINE,
        }:
            return OperationResult.failure(err.INCOMPLETE, err.MESSAGES[err.INCOMPLETE])
    return None


def try_fire_on_arrival(watch: Watch, batch: WatchBatch) -> OperationResult:
    """Tras intake OK: si on_arrival, claim del lote e intenta encolar."""
    if watch.fire_mode != Watch.FIRE_ON_ARRIVAL:
        return OperationResult.success(user_message="")
    if watch.status != Watch.STATUS_ACTIVE:
        return OperationResult.failure(err.INACTIVE, err.MESSAGES[err.INACTIVE])
    if watch.route_mode == Watch.ROUTE_DEFER:
        return OperationResult.failure(
            err.FIRE_ROUTE_CONFLICT, err.MESSAGES[err.FIRE_ROUTE_CONFLICT]
        )

    from apps.file_scheduler.services import schedule_runner as runner_svc

    with transaction.atomic():
        locked = (
            WatchBatch.objects.select_for_update()
            .filter(pk=batch.pk, status=WatchBatch.STATUS_PENDING)
            .first()
        )
        if locked is None:
            return OperationResult.success(user_message="")
        now = timezone.now()
        locked.status = WatchBatch.STATUS_CLAIMED
        locked.save(update_fields=["status", "updated_at"])
        locked.status = WatchBatch.STATUS_CONSUMED
        locked.consumed_at = now
        locked.consumed_by = "fire:pending"
        locked.save(update_fields=["status", "consumed_at", "consumed_by", "updated_at"])
        claimed = locked

    upload = runner_svc.wrap_stored_upload(
        claimed.storage_key, claimed.original_filename or "file"
    )
    if upload is None:
        _revert_pending(claimed, err.FIRE_FAILED)
        audit_svc.append_event(
            watch,
            WatchAuditEvent.EVENT_FIRE_FAILED,
            None,
            {
                "triggered_by": "system:file_watch",
                "batch_id": str(claimed.id),
                "error_code": err.FIRE_FAILED,
            },
        )
        from apps.file_watch.services import watch_notify as notify_svc

        notify_svc.dispatch_for_batch(watch, claimed, kind="fire_failed")
        return OperationResult.failure(err.FIRE_FAILED, err.MESSAGES[err.FIRE_FAILED])

    try:
        result = _enqueue_route(watch, upload, claimed)
    except Exception:
        logger.exception("try_fire_on_arrival enqueue watch=%s", watch.pk)
        result = OperationResult.failure(err.FIRE_FAILED, err.MESSAGES[err.FIRE_FAILED])

    if not result.ok:
        _revert_pending(claimed, result.error_code or err.FIRE_FAILED)
        audit_svc.append_event(
            watch,
            WatchAuditEvent.EVENT_FIRE_FAILED,
            None,
            {
                "triggered_by": "system:file_watch",
                "batch_id": str(claimed.id),
                "error_code": result.error_code or err.FIRE_FAILED,
            },
        )
        from apps.file_watch.services import watch_notify as notify_svc

        notify_svc.dispatch_for_batch(watch, claimed, kind="fire_failed")
        return result

    job = (result.payload or {}).get("job")
    run = (result.payload or {}).get("run")
    job_id = str(job.id) if job is not None else ""
    run_id = str(run.id) if run is not None else ""
    by = f"fire:{job_id or run_id or 'ok'}"
    claimed.consumed_by = by[:128]
    claimed.job_id = job_id[:36]
    claimed.pipeline_run_id = run_id[:36]
    claimed.error_code = ""
    claimed.save(
        update_fields=[
            "consumed_by",
            "job_id",
            "pipeline_run_id",
            "error_code",
            "updated_at",
        ]
    )
    audit_svc.append_event(
        watch,
        WatchAuditEvent.EVENT_FIRED,
        None,
        {
            "triggered_by": "system:file_watch",
            "batch_id": str(claimed.id),
            "job_id": job_id,
            "pipeline_run_id": run_id,
        },
    )
    return result


def _revert_pending(batch: WatchBatch, error_code: str) -> None:
    batch.status = WatchBatch.STATUS_PENDING
    batch.consumed_at = None
    batch.consumed_by = ""
    batch.error_code = error_code
    batch.save(
        update_fields=[
            "status",
            "consumed_at",
            "consumed_by",
            "error_code",
            "updated_at",
        ]
    )


def _enqueue_route(watch: Watch, upload, batch: WatchBatch) -> OperationResult:
    actor = watch.owner
    if watch.route_mode == Watch.ROUTE_JOB and watch.route_project_id:
        project = watch.route_project
        kind = (watch.route_kind or "").strip()
        from apps.file_scheduler.services import schedule_runner as runner_svc

        if kind == "file_clean":
            from apps.file_clean.run.services import clean_run_service

            return clean_run_service.run_clean_job(
                actor,
                project,
                None,
                upload,
                require_membership=False,
                idempotency_key=f"watch:{watch.id}:{batch.id}",
            )
        if kind == "file_gate":
            from apps.file_gate.run.services import validation_run_service

            return validation_run_service.validate_and_run(
                actor, project, upload, require_membership=False
            )
        if kind == "dms":
            return runner_svc._run_dms(actor, project, upload)
        return OperationResult.failure(err.FIRE_FAILED, err.MESSAGES[err.FIRE_FAILED])

    if watch.route_mode == Watch.ROUTE_PIPELINE and watch.route_pipeline_id:
        from apps.file_pipeline.services import pipeline_run_service

        return pipeline_run_service.start_run(
            actor,
            watch.route_pipeline,
            upload,
            dry_run=False,
            require_membership=False,
            trigger_source="file_watch",
            correlation_id=str(batch.id),
        )
    return OperationResult.failure(err.NO_PUBLISHED, err.MESSAGES[err.NO_PUBLISHED])
