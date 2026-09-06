from __future__ import annotations

from apps.platform_api.models import (
    ACTION_CHOICES,
    ACTION_CREATED,
    ACTION_KEY_REVEALED,
    ACTION_KEY_ROTATED,
    ACTION_REVOKED,
    ACTION_UPDATED,
    ApiClient,
    ApiClientAuditEvent,
)

MSG_EVENT_NOT_FOUND = "No se encontró el evento de auditoría."
MSG_US_ONLY = "Solo el administrador de compañía (US) puede consultar la auditoría de API."

SUMMARIES = {
    ACTION_CREATED: "Se creó el cliente de máquina y se emitió la key.",
    ACTION_UPDATED: "Se cambió código, nombre, descripción o scopes. La key no se regeneró.",
    ACTION_KEY_ROTATED: "Se rotó la key. La anterior deja de autenticar.",
    ACTION_REVOKED: "Se revocó el cliente. Ya no puede autenticar llamadas.",
    ACTION_KEY_REVEALED: "Un US vio la key en claro (pantalla de un solo uso).",
}


def snapshot_client(client: ApiClient) -> dict:
    return {
        "code": client.code,
        "name": client.name,
        "description": client.description,
        "environment": client.environment,
        "status": client.status,
        "scopes": list(client.scopes or []),
        "key_hint": client.key_hint,
        "webhook_url": client.webhook_url,
        "webhook_enabled": bool(client.webhook_enabled),
        "webhook_events": list(client.webhook_events or []),
    }


def request_meta(request) -> tuple[str, str]:
    if request is None:
        return "", ""
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    ip = forwarded or (request.META.get("REMOTE_ADDR") or "")
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:256]
    return ip[:64], ua


def record_event(
    *,
    client: ApiClient,
    action: str,
    actor,
    request=None,
    before: dict | None = None,
    after: dict | None = None,
) -> ApiClientAuditEvent:
    ip, ua = request_meta(request)
    return ApiClientAuditEvent.objects.create(
        company_id=client.company_id,
        client=client,
        action=action,
        summary=SUMMARIES.get(action, action),
        before=before,
        after=after,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        ip_address=ip,
        user_agent=ua,
    )


def list_for_user(user, *, action: str = "", client: ApiClient | None = None):
    from apps.platform_api.services.api_client_service import can_manage

    if not can_manage(user):
        return [], {"total": 0}
    qs = (
        ApiClientAuditEvent.objects.filter(company_id=user.profile.company_id)
        .select_related("client", "actor")
    )
    if client is not None:
        qs = qs.filter(client=client)
    if action:
        qs = qs.filter(action=action)
    rows = list(qs[:500])
    return rows, {"total": len(rows)}


def get_event_for_user(user, pk) -> ApiClientAuditEvent | None:
    from apps.platform_api.services.api_client_service import can_manage

    if not can_manage(user):
        return None
    return (
        ApiClientAuditEvent.objects.filter(pk=pk, company_id=user.profile.company_id)
        .select_related("client", "actor", "company")
        .first()
    )


def list_for_client_user(user, client_pk):
    from apps.platform_api.services.api_client_service import get_for_user

    client = get_for_user(user, client_pk)
    if client is None:
        return None, [], {}
    rows, stats = list_for_user(user, client=client)
    return client, rows, stats


def action_choices():
    return ACTION_CHOICES
