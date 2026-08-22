"""Historial y auditoría de corridas File Pipeline (M5)."""

from __future__ import annotations

import logging
from datetime import datetime, time
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.core.services.operation_result import OperationResult
from apps.file_pipeline.models import PipelineDefinition, PipelineMembership, PipelineRun
from apps.file_pipeline.services import pipeline_project_service as lifecycle
from apps.file_pipeline.services import pipeline_run_service as run_svc

MSG_NO_HISTORY = "No tiene permiso para ver el historial de este pipeline."
MSG_NOT_FOUND = "No se encontró la corrida en este pipeline."
MSG_DELETED = "Corrida eliminada del historial."
MSG_DELETED_MANY = "Se eliminaron {n} corridas propias del historial."
MSG_NONE_OWN = "No tiene corridas propias para eliminar en este pipeline."
MSG_NOT_OWNER = "Solo puede eliminar corridas que usted ejecutó."
MSG_IN_PROGRESS = "No se puede eliminar un job en ejecución."
MSG_UNEXPECTED = (
    "No se pudo eliminar la corrida. Si el problema continúa, contacte al administrador."
)

PAGE_SIZE = 25
STATUS_ALL = "all"
TRIGGER_ALL = "all"
NON_FINAL = (PipelineRun.STATUS_QUEUED, PipelineRun.STATUS_RUNNING)

logger = logging.getLogger(__name__)

STATUS_FILTERABLE = {
    PipelineRun.STATUS_COMPLETED,
    PipelineRun.STATUS_FAILED,
    PipelineRun.STATUS_RUNNING,
    PipelineRun.STATUS_QUEUED,
    PipelineRun.STATUS_CANCELLED,
}

TRIGGER_FILTERABLE = {code for code, _label in PipelineRun.TRIGGER_CHOICES}


def user_can_view_history(user, pipeline: PipelineDefinition) -> bool:
    return lifecycle.user_can_view(user, pipeline)


def resolve_role(user, pipeline: PipelineDefinition) -> str:
    membership = lifecycle.get_membership(user, pipeline)
    if membership is not None:
        return membership.role
    return PipelineMembership.ROLE_CO


def user_can_see_job_links(user, pipeline: PipelineDefinition) -> bool:
    return resolve_role(user, pipeline) != PipelineMembership.ROLE_CO


def run_is_final(run: PipelineRun) -> bool:
    return run.status not in NON_FINAL


def can_delete_run(user, pipeline: PipelineDefinition, run: PipelineRun) -> bool:
    if not user_can_view_history(user, pipeline):
        return False
    if not run_is_final(run):
        return False
    if resolve_role(user, pipeline) == PipelineMembership.ROLE_PA:
        return True
    return bool(run.triggered_by_id) and run.triggered_by_id == user.id


def trigger_options() -> list[dict]:
    return [
        {"value": code, "label": label}
        for code, label in PipelineRun.TRIGGER_CHOICES
    ]


def status_options() -> list[dict]:
    return [
        {"value": code, "label": label}
        for code, label in PipelineRun.STATUS_CHOICES
        if code in STATUS_FILTERABLE
    ]


def parse_filters(params) -> tuple[dict, dict]:
    errors: dict[str, list[str]] = {}
    status = (params.get("status") or STATUS_ALL).strip()
    if status not in STATUS_FILTERABLE and status != STATUS_ALL:
        status = STATUS_ALL
        errors.setdefault("status", []).append("Estado de corrida no válido.")

    trigger = (params.get("trigger") or TRIGGER_ALL).strip()
    if trigger not in TRIGGER_FILTERABLE and trigger != TRIGGER_ALL:
        trigger = TRIGGER_ALL
        errors.setdefault("trigger", []).append("Canal de disparo no válido.")

    date_from_raw = (params.get("date_from") or "").strip()
    date_to_raw = (params.get("date_to") or "").strip()
    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None
    if date_from_raw and date_from is None:
        errors.setdefault("date_from", []).append("Fecha desde no válida.")
    if date_to_raw and date_to is None:
        errors.setdefault("date_to", []).append("Fecha hasta no válida.")
    if date_from and date_to and date_from > date_to:
        errors.setdefault("date_to", []).append("La fecha hasta no puede ser anterior a desde.")

    try:
        page = max(1, int(params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1

    filters = {
        "status": status,
        "trigger": trigger,
        "date_from": date_from.isoformat() if date_from else "",
        "date_to": date_to.isoformat() if date_to else "",
        "date_from_obj": date_from,
        "date_to_obj": date_to,
        "page": page,
    }
    return filters, errors


def _apply_filters(qs, filters: dict):
    if filters["status"] != STATUS_ALL:
        qs = qs.filter(status=filters["status"])
    if filters["trigger"] != TRIGGER_ALL:
        qs = qs.filter(trigger_source=filters["trigger"])
    tz = timezone.get_current_timezone()
    if filters["date_from_obj"]:
        start = timezone.make_aware(
            datetime.combine(filters["date_from_obj"], time.min), tz
        )
        qs = qs.filter(created_at__gte=start)
    if filters["date_to_obj"]:
        end = timezone.make_aware(
            datetime.combine(filters["date_to_obj"], time.max), tz
        )
        qs = qs.filter(created_at__lte=end)
    return qs


def querystring(filters: dict, *, page: int | None = None) -> str:
    data = {
        "status": filters["status"],
        "trigger": filters["trigger"],
        "date_from": filters["date_from"],
        "date_to": filters["date_to"],
    }
    if page and page > 1:
        data["page"] = str(page)
    return urlencode({k: v for k, v in data.items() if v and v != STATUS_ALL})


def actor_label(run: PipelineRun) -> str:
    if run.trigger_source == PipelineRun.TRIGGER_API and run.api_client_label:
        return run.api_client_label
    if run.triggered_by_id:
        user = run.triggered_by
        return user.get_username() if user else f"#{run.triggered_by_id}"
    if run.trigger_source == PipelineRun.TRIGGER_WATCH:
        return "sistema / watch"
    if run.trigger_source == PipelineRun.TRIGGER_SCHEDULER:
        return "sistema / scheduler"
    if run.trigger_source == PipelineRun.TRIGGER_DEPENDENCY:
        return "dependencia"
    return "—"


def duration_label(run: PipelineRun) -> str:
    if run.duration_ms is None:
        return "—"
    return f"{run.duration_ms / 1000:.1f}s"


def list_context(user, pipeline: PipelineDefinition, params) -> dict:
    filters, errors = parse_filters(params)
    base = pipeline.runs.select_related("version", "triggered_by")
    stats = {
        "total": base.count(),
        "completed": base.filter(status=PipelineRun.STATUS_COMPLETED).count(),
        "failed": base.filter(status=PipelineRun.STATUS_FAILED).count(),
        "ui": base.filter(trigger_source=PipelineRun.TRIGGER_UI).count(),
    }
    filtered = _apply_filters(base, filters)
    paginator = Paginator(filtered, PAGE_SIZE)
    page_obj = paginator.get_page(filters["page"])
    rows = []
    for run in page_obj.object_list:
        rows.append(
            {
                "run": run,
                "actor": actor_label(run),
                "duration": duration_label(run),
                "version_label": f"v{run.version.version_number}",
                "hash_short": (run.input_sha256[:12] + "…") if run.input_sha256 else "—",
                "can_delete": can_delete_run(user, pipeline, run),
            }
        )
    has_active = any(
        [
            filters["status"] != STATUS_ALL,
            filters["trigger"] != TRIGGER_ALL,
            filters["date_from"],
            filters["date_to"],
        ]
    )
    return {
        "filters": filters,
        "errors": errors,
        "stats": stats,
        "rows": rows,
        "page_obj": page_obj,
        "qs": querystring(filters),
        "qs_prev": querystring(filters, page=page_obj.previous_page_number())
        if page_obj.has_previous()
        else "",
        "qs_next": querystring(filters, page=page_obj.next_page_number())
        if page_obj.has_next()
        else "",
        "has_any": stats["total"] > 0,
        "has_active_filters": has_active,
        "trigger_options": trigger_options(),
        "status_options": status_options(),
        "can_execute": run_svc.user_can_execute_pipeline(user, pipeline),
        "can_see_job_links": user_can_see_job_links(user, pipeline),
        "role": resolve_role(user, pipeline),
        "page_size": PAGE_SIZE,
        "can_delete_own_any": _own_final_qs(user, pipeline).exists(),
    }


def audit_context(user, pipeline: PipelineDefinition, run: PipelineRun) -> dict:
    show_links = user_can_see_job_links(user, pipeline)
    return {
        "run": run,
        "actor": actor_label(run),
        "duration": duration_label(run),
        "step_rows": run_svc.step_view_rows(run, show_job_links=show_links),
        "can_see_job_links": show_links,
        "role": resolve_role(user, pipeline),
        "is_co": resolve_role(user, pipeline) == PipelineMembership.ROLE_CO,
        "can_delete": can_delete_run(user, pipeline, run),
    }


def _own_final_qs(user, pipeline: PipelineDefinition):
    return pipeline.runs.filter(triggered_by=user).exclude(status__in=NON_FINAL)


def delete_run(user, pipeline: PipelineDefinition, run_id) -> OperationResult:
    if not user_can_view_history(user, pipeline):
        return OperationResult.failure("forbidden", MSG_NO_HISTORY)
    run = pipeline.runs.filter(id=run_id).first()
    if run is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    if not run_is_final(run):
        return OperationResult.failure("conflict", MSG_IN_PROGRESS)
    if not can_delete_run(user, pipeline, run):
        return OperationResult.failure("forbidden", MSG_NOT_OWNER)
    try:
        run.delete()
    except Exception:
        logger.exception("delete pipeline run failed pipeline=%s run=%s", pipeline.id, run_id)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(MSG_DELETED)


def delete_own_runs(user, pipeline: PipelineDefinition) -> OperationResult:
    if not user_can_view_history(user, pipeline):
        return OperationResult.failure("forbidden", MSG_NO_HISTORY)
    runs = list(_own_final_qs(user, pipeline))
    if not runs:
        return OperationResult.failure("not_found", MSG_NONE_OWN)
    deleted = 0
    try:
        for run in runs:
            run.delete()
            deleted += 1
    except Exception:
        logger.exception(
            "delete own pipeline runs failed pipeline=%s user=%s deleted=%s",
            pipeline.id,
            user.id,
            deleted,
        )
        if deleted:
            return OperationResult.success(
                MSG_DELETED_MANY.format(n=deleted), payload={"deleted_count": deleted}
            )
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(
        MSG_DELETED_MANY.format(n=deleted), payload={"deleted_count": deleted}
    )
