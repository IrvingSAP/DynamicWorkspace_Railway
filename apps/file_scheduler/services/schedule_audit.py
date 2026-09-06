"""M7: presentación append-only de auditoría (definición + tick)."""

from __future__ import annotations

from apps.file_scheduler.models import ScheduleAuditEvent

SYSTEM_ACTOR = "system:scheduler"

PLANE_DEFINITION = "definition"
PLANE_TICK = "tick"

DEFINITION_EVENTS = frozenset(
    {
        ScheduleAuditEvent.EVENT_CREATED,
        ScheduleAuditEvent.EVENT_UPDATED,
        ScheduleAuditEvent.EVENT_PAUSED,
        ScheduleAuditEvent.EVENT_RESUMED,
        ScheduleAuditEvent.EVENT_ARCHIVED,
    }
)
TICK_EVENTS = frozenset(
    {
        ScheduleAuditEvent.EVENT_TICK_ENQUEUED,
        ScheduleAuditEvent.EVENT_TICK_SKIPPED,
        ScheduleAuditEvent.EVENT_TICK_FAILED,
        ScheduleAuditEvent.EVENT_NOTIFY_SENT,
    }
)

EVENT_LABELS = dict(ScheduleAuditEvent.EVENT_CHOICES)

_SKIP_KEYS = {
    "company_id",
    "schedule_id",
    "status_unchanged",
    "triggered_by",
}


def list_audit_rows(schedule) -> list[dict]:
    events = list(
        ScheduleAuditEvent.objects.filter(schedule=schedule)
        .select_related("actor")
        .order_by("-created_at")
    )
    hrefs = _pipeline_run_hrefs(
        [
            str((ev.payload or {}).get("pipeline_run_id") or "")
            for ev in events
            if isinstance(ev.payload, dict)
        ]
    )
    rows = []
    for ev in events:
        row = audit_row(ev)
        rid = row.get("pipeline_run_id") or ""
        row["run_href"] = hrefs.get(rid, "")
        rows.append(row)
    return rows


def audit_row(event: ScheduleAuditEvent) -> dict:
    payload = event.payload if isinstance(event.payload, dict) else {}
    plane = PLANE_TICK if event.event in TICK_EVENTS else PLANE_DEFINITION
    job_id = str(payload.get("job_id") or "")
    run_id = str(payload.get("pipeline_run_id") or "")
    return {
        "event": event,
        "occurred_at": event.created_at,
        "event_code": event.event,
        "event_label": EVENT_LABELS.get(event.event, event.event),
        "plane": plane,
        "actor_label": _actor_label(event, payload),
        "summary": _summary(event.event, payload),
        "correlation_id": str(payload.get("correlation_id") or "")[:16],
        "job_id": job_id,
        "pipeline_run_id": run_id,
        "run_label": _run_label(job_id, run_id),
        "error_code": str(payload.get("error_code") or ""),
    }


def _actor_label(event: ScheduleAuditEvent, payload: dict) -> str:
    if event.actor_id:
        return event.actor.username
    triggered = str(payload.get("triggered_by") or "").strip()
    if triggered:
        return triggered
    if event.event in TICK_EVENTS:
        return SYSTEM_ACTOR
    return "—"


def _pipeline_run_hrefs(run_ids: list[str]) -> dict[str, str]:
    import uuid

    from django.urls import reverse

    from apps.file_pipeline.models import PipelineRun

    valid = []
    for rid in run_ids:
        if not rid:
            continue
        try:
            valid.append(uuid.UUID(str(rid)))
        except (ValueError, TypeError, AttributeError):
            continue
    if not valid:
        return {}
    mapping = {}
    for run in PipelineRun.objects.filter(pk__in=valid).select_related("pipeline"):
        mapping[str(run.id)] = reverse(
            "file_pipeline:pipeline_run_result",
            kwargs={"pipeline_slug": run.pipeline.slug, "run_id": run.id},
        )
    return mapping


def _run_label(job_id: str, run_id: str) -> str:
    if run_id:
        return f"pipeline {run_id[:8]}"
    if job_id:
        return f"job {job_id[:8]}"
    return ""


def _summary(event_code: str, payload: dict) -> str:
    if event_code == ScheduleAuditEvent.EVENT_CREATED:
        slug = payload.get("slug") or ""
        return f"Alta {slug}".strip() or "Alta del plan"
    if event_code == ScheduleAuditEvent.EVENT_PAUSED:
        return f"{payload.get('from') or 'active'} → {payload.get('to') or 'inactive'}"
    if event_code == ScheduleAuditEvent.EVENT_RESUMED:
        return f"{payload.get('from') or 'inactive'} → {payload.get('to') or 'active'}"
    if event_code == ScheduleAuditEvent.EVENT_ARCHIVED:
        return "Archivado"
    if event_code == ScheduleAuditEvent.EVENT_TICK_ENQUEUED:
        src = payload.get("trigger_source") or "scheduler"
        corr = str(payload.get("correlation_id") or "")[:8]
        bits = [f"encolado ({src})"]
        if corr:
            bits.append(corr)
        return " · ".join(bits)
    if event_code in {
        ScheduleAuditEvent.EVENT_TICK_SKIPPED,
        ScheduleAuditEvent.EVENT_TICK_FAILED,
    }:
        from apps.file_scheduler.services import schedule_errors as err

        code = str(payload.get("error_code") or "")
        return err.message_for(code) or code or "tick"
    if event_code == ScheduleAuditEvent.EVENT_NOTIFY_SENT:
        return str(payload.get("channel") or "aviso")
    keys = [
        k
        for k in payload.keys()
        if k not in _SKIP_KEYS and payload.get(k) not in ("", None, False)
    ]
    if not keys:
        return "Actualizado"
    return ", ".join(keys[:6])
