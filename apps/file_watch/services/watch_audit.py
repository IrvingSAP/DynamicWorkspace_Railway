"""M7: helper append-only de auditoría (definición + llegada)."""

from __future__ import annotations

from apps.file_watch.models import Watch, WatchAuditEvent

SYSTEM_ACTOR = "system:file_watch"

PLANE_DEFINITION = "definition"
PLANE_ARRIVAL = "arrival"

DEFINITION_EVENTS = frozenset(
    {
        WatchAuditEvent.EVENT_CREATED,
        WatchAuditEvent.EVENT_UPDATED,
        WatchAuditEvent.EVENT_PAUSED,
        WatchAuditEvent.EVENT_RESUMED,
        WatchAuditEvent.EVENT_ARCHIVED,
        WatchAuditEvent.EVENT_SOURCE_UPDATED,
        WatchAuditEvent.EVENT_SOURCE_TESTED,
        WatchAuditEvent.EVENT_PUSH_TOKEN_ROTATED,
        WatchAuditEvent.EVENT_ROUTE_UPDATED,
        WatchAuditEvent.EVENT_FIRE_UPDATED,
        WatchAuditEvent.EVENT_INTAKE_POLICY_UPDATED,
        WatchAuditEvent.EVENT_IDEMPOTENCY_UPDATED,
        WatchAuditEvent.EVENT_NOTIFY_UPDATED,
    }
)
ARRIVAL_EVENTS = frozenset(
    {
        WatchAuditEvent.EVENT_BATCH_INGESTED,
        WatchAuditEvent.EVENT_BATCH_SKIPPED,
        WatchAuditEvent.EVENT_BATCH_INTAKE_FAILED,
        WatchAuditEvent.EVENT_BATCH_CLAIM,
        WatchAuditEvent.EVENT_FIRED,
        WatchAuditEvent.EVENT_FIRE_FAILED,
        WatchAuditEvent.EVENT_FIRE_SKIPPED,
        WatchAuditEvent.EVENT_RETRY_SCHEDULED,
        WatchAuditEvent.EVENT_NOTIFY_SENT,
    }
)

EVENT_LABELS = dict(WatchAuditEvent.EVENT_CHOICES)


def append_event(
    watch: Watch,
    event: str,
    actor=None,
    payload: dict | None = None,
) -> WatchAuditEvent:
    body = dict(payload or {})
    body.setdefault("company_id", str(watch.company_id))
    body.setdefault("watch_id", str(watch.id))
    body.setdefault("slug", watch.slug)
    return WatchAuditEvent.objects.create(
        company_id=watch.company_id,
        watch=watch,
        event=event,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        payload=body,
    )


def list_audit_rows(watch: Watch) -> list[dict]:
    events = list(
        WatchAuditEvent.objects.filter(watch=watch)
        .select_related("actor")
        .order_by("-created_at")
    )
    rows = []
    for ev in events:
        rows.append(audit_row(ev))
    return rows


def audit_row(event: WatchAuditEvent) -> dict:
    payload = event.payload if isinstance(event.payload, dict) else {}
    plane = PLANE_ARRIVAL if event.event in ARRIVAL_EVENTS else PLANE_DEFINITION
    return {
        "event": event,
        "occurred_at": event.created_at,
        "event_code": event.event,
        "event_label": EVENT_LABELS.get(event.event, event.event),
        "plane": plane,
        "actor_label": _actor_label(event, payload),
        "summary": _summary(event.event, payload),
        "correlation_id": str(payload.get("correlation_id") or "")[:16],
        "job_id": str(payload.get("job_id") or ""),
        "pipeline_run_id": str(payload.get("pipeline_run_id") or ""),
        "batch_id": str(payload.get("batch_id") or ""),
        "error_code": str(payload.get("error_code") or ""),
    }


def _actor_label(event: WatchAuditEvent, payload: dict) -> str:
    if event.actor_id:
        return event.actor.username
    triggered = str(payload.get("triggered_by") or "").strip()
    if triggered:
        return triggered
    if event.event in ARRIVAL_EVENTS:
        return SYSTEM_ACTOR
    return "—"


def _summary(event_code: str, payload: dict) -> str:
    if event_code == WatchAuditEvent.EVENT_CREATED:
        slug = payload.get("slug") or ""
        return f"Alta {slug}".strip() or "Alta de la bandeja"
    if event_code == WatchAuditEvent.EVENT_PAUSED:
        return f"{payload.get('from') or 'active'} → {payload.get('to') or 'inactive'}"
    if event_code == WatchAuditEvent.EVENT_RESUMED:
        return f"{payload.get('from') or 'inactive'} → {payload.get('to') or 'active'}"
    if event_code == WatchAuditEvent.EVENT_ARCHIVED:
        return "Archivado"
    if event_code == WatchAuditEvent.EVENT_BATCH_INGESTED:
        name = payload.get("filename") or payload.get("original_filename") or ""
        return f"Ingerido {name}".strip() or "Lote ingerido"
    if event_code in {
        WatchAuditEvent.EVENT_BATCH_SKIPPED,
        WatchAuditEvent.EVENT_BATCH_INTAKE_FAILED,
        WatchAuditEvent.EVENT_FIRE_FAILED,
    }:
        from apps.file_watch.services import watch_errors as err

        code = str(payload.get("error_code") or "")
        return err.message_for(code) or code or event_code
    if event_code == WatchAuditEvent.EVENT_NOTIFY_SENT:
        return str(payload.get("channel") or "aviso")
    keys = [
        k
        for k in payload.keys()
        if k not in {"company_id", "watch_id", "slug", "status_unchanged"}
        and payload.get(k) not in ("", None, False)
    ]
    if not keys:
        return "Actualizado"
    return ", ".join(keys[:6])
