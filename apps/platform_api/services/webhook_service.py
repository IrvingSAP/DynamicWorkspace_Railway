from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.platform_api.models import (
    ACTION_UPDATED,
    DELIVERY_DELIVERED,
    DELIVERY_FAILED,
    DELIVERY_PENDING,
    EVENT_JOB_CANCELLED,
    EVENT_JOB_COMPLETED,
    EVENT_JOB_FAILED,
    STATUS_REVOKED,
    WEBHOOK_EVENTS,
    ApiClient,
    ApiWebhookDelivery,
)
from apps.platform_api.services import client_audit_service, process_security_service
from apps.platform_api.services.api_client_service import can_manage
from apps.platform_api.services.contract_service import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
)

logger = logging.getLogger(__name__)

MSG_SAVED = "Webhook del cliente actualizado."
MSG_DISABLED = "Webhook desactivado."
MSG_VALIDATION = "Revise los datos marcados; no se pudo guardar."
MSG_US_ONLY = "Solo el administrador de compañía (US) puede gestionar clientes de API."
MSG_REVOKED = "Este cliente ya está revocado."
MSG_NEED_URL = "Indique la URL HTTPS del callback."
MSG_NEED_EVENTS = "Seleccione al menos un evento."

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (0, 15, 60, 300, 900)
POST_TIMEOUT = 8
SIGNATURE_HEADER = "X-Platform-Signature"
EVENT_HEADER = "X-Platform-Event"
TIMESTAMP_HEADER = "X-Platform-Timestamp"

EVENT_BY_STATUS = {
    STATUS_COMPLETED: EVENT_JOB_COMPLETED,
    STATUS_FAILED: EVENT_JOB_FAILED,
    STATUS_CANCELLED: EVENT_JOB_CANCELLED,
}


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def signatures_match(secret: str, body: bytes, header: str) -> bool:
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected, (header or "").strip())


def event_for_status(status: str) -> str | None:
    return EVENT_BY_STATUS.get(status)


def _minimal_payload(event: str, envelope: dict) -> dict:
    job_id = envelope.get("job_id")
    artifacts = envelope.get("artifacts") or {}
    audit = envelope.get("audit") or {}
    links = {"self": f"/api/v1/jobs/{job_id}" if job_id else None}
    if artifacts.get("report_url"):
        links["report"] = artifacts["report_url"]
    if artifacts.get("output_url"):
        links["output"] = artifacts["output_url"]
    return {
        "event": event,
        "job_id": job_id,
        "pipeline_run_id": envelope.get("pipeline_run_id"),
        "kind": envelope.get("kind"),
        "status": envelope.get("status"),
        "ok": bool(envelope.get("ok")),
        "correlation_id": audit.get("correlation_id") or envelope.get("correlation_id"),
        "failed_step_id": (envelope.get("summary") or {}).get("failed_step_order"),
        "links": {key: value for key, value in links.items() if value},
    }


def posted_from_request(post) -> dict:
    events = post.getlist("webhook_events") if hasattr(post, "getlist") else post.get("webhook_events") or []
    if isinstance(events, str):
        events = [events]
    enabled_raw = post.get("webhook_enabled")
    return {
        "webhook_url": (post.get("webhook_url") or "").strip(),
        "webhook_secret": (post.get("webhook_secret") or "").strip(),
        "rotate_secret": str(post.get("rotate_secret") or "").lower() in {"1", "true", "on", "yes"},
        "webhook_enabled": str(enabled_raw or "").lower() in {"1", "true", "on", "yes"},
        "webhook_events": [item for item in events if item in WEBHOOK_EVENTS],
    }


def update_webhook(user, client: ApiClient, posted: dict, request=None) -> OperationResult:
    if not can_manage(user) or client.company_id != getattr(user.profile, "company_id", None):
        return OperationResult.failure("forbidden", MSG_US_ONLY)
    if client.status == STATUS_REVOKED:
        return OperationResult.failure("forbidden", MSG_REVOKED)

    enabled = bool(posted.get("webhook_enabled"))
    url = posted.get("webhook_url") or ""
    events = posted.get("webhook_events") or []
    errors: dict[str, list[str]] = {}
    new_secret = ""

    if enabled:
        if not url:
            errors["webhook_url"] = [MSG_NEED_URL]
        else:
            url_result = process_security_service.validate_callback_url(url, client.company)
            if not url_result.ok:
                errors["webhook_url"] = (url_result.errors or {}).get("callback_url") or [
                    process_security_service.MSG_CALLBACK
                ]
        if not events:
            errors["webhook_events"] = [MSG_NEED_EVENTS]
        if posted.get("rotate_secret") or not client.webhook_secret:
            new_secret = posted.get("webhook_secret") or secrets.token_urlsafe(32)
        elif posted.get("webhook_secret"):
            new_secret = posted["webhook_secret"]
    elif url:
        url_result = process_security_service.validate_callback_url(url, client.company)
        if not url_result.ok:
            errors["webhook_url"] = (url_result.errors or {}).get("callback_url") or [
                process_security_service.MSG_CALLBACK
            ]

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    before = client_audit_service.snapshot_client(client)
    client.webhook_url = url
    client.webhook_enabled = enabled and bool(url)
    client.webhook_events = events or list(WEBHOOK_EVENTS)
    if new_secret:
        client.webhook_secret = new_secret
        client.webhook_secret_hint = new_secret[-4:]
    client.save(
        update_fields=[
            "webhook_url",
            "webhook_enabled",
            "webhook_events",
            "webhook_secret",
            "webhook_secret_hint",
            "updated_at",
        ]
    )
    after = client_audit_service.snapshot_client(client)
    if before != after:
        client_audit_service.record_event(
            client=client,
            action=ACTION_UPDATED,
            actor=user,
            request=request,
            before=before,
            after=after,
        )
    message = MSG_SAVED if client.webhook_enabled else MSG_DISABLED
    return OperationResult.success(
        message,
        client=client,
        plaintext_webhook_secret=new_secret or "",
    )


def notify_from_envelope(client: ApiClient, envelope: dict) -> ApiWebhookDelivery | None:
    if not client.webhook_enabled or not client.webhook_url or not client.webhook_secret:
        return None
    event = event_for_status(str(envelope.get("status") or ""))
    if event is None:
        return None
    subscribed = client.webhook_events or list(WEBHOOK_EVENTS)
    if event not in subscribed:
        return None
    url_result = process_security_service.validate_callback_url(client.webhook_url, client.company)
    if not url_result.ok:
        logger.info("webhook skipped: url not allowlisted client=%s", client.pk)
        return None
    job_id = envelope.get("job_id") or envelope.get("pipeline_run_id")
    if not job_id:
        return None
    payload = _minimal_payload(event, envelope)
    delivery = ApiWebhookDelivery.objects.create(
        company_id=client.company_id,
        client=client,
        event=event,
        job_id=job_id,
        payload=payload,
        status=DELIVERY_PENDING,
        max_attempts=MAX_ATTEMPTS,
        next_retry_at=timezone.now(),
    )
    deliver_once(delivery)
    return delivery


def deliver_once(delivery: ApiWebhookDelivery) -> None:
    client = delivery.client
    if delivery.attempt_count >= delivery.max_attempts:
        delivery.status = DELIVERY_FAILED
        delivery.save(update_fields=["status", "updated_at"])
        return
    body = json.dumps(delivery.payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(timezone.now().timestamp()))
    headers = {
        "Content-Type": "application/json",
        EVENT_HEADER: delivery.event,
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: sign_payload(client.webhook_secret, body),
        "User-Agent": "DynamicWorkspace-PlatformAPI/1.0",
    }
    request = Request(client.webhook_url, data=body, headers=headers, method="POST")
    delivery.attempt_count += 1
    try:
        with urlopen(request, timeout=POST_TIMEOUT) as response:
            code = int(getattr(response, "status", 200) or 200)
        if 200 <= code < 300:
            delivery.status = DELIVERY_DELIVERED
            delivery.response_status = code
            delivery.last_error = ""
            delivery.delivered_at = timezone.now()
            delivery.next_retry_at = None
            delivery.save(
                update_fields=[
                    "attempt_count",
                    "status",
                    "response_status",
                    "last_error",
                    "delivered_at",
                    "next_retry_at",
                    "updated_at",
                ]
            )
            return
        delivery.response_status = code
        delivery.last_error = f"HTTP {code}"
    except HTTPError as exc:
        delivery.response_status = int(getattr(exc, "code", 0) or 0)
        delivery.last_error = f"HTTP {delivery.response_status}"[:240]
    except (URLError, TimeoutError, OSError):
        logger.exception("webhook delivery failed id=%s", delivery.pk)
        delivery.last_error = "No se pudo contactar el callback."
    if delivery.attempt_count >= delivery.max_attempts:
        delivery.status = DELIVERY_FAILED
        delivery.next_retry_at = None
    else:
        wait = BACKOFF_SECONDS[min(delivery.attempt_count, len(BACKOFF_SECONDS) - 1)]
        delivery.status = DELIVERY_PENDING
        delivery.next_retry_at = timezone.now() + timedelta(seconds=wait)
    delivery.save(
        update_fields=[
            "attempt_count",
            "status",
            "response_status",
            "last_error",
            "next_retry_at",
            "updated_at",
        ]
    )


def process_due_retries(*, limit: int = 20) -> int:
    now = timezone.now()
    due = list(
        ApiWebhookDelivery.objects.select_related("client", "client__company")
        .filter(status=DELIVERY_PENDING, next_retry_at__lte=now)
        .order_by("next_retry_at")[:limit]
    )
    for row in due:
        deliver_once(row)
    return len(due)


def recent_for_client(client: ApiClient, *, limit: int = 12):
    return list(client.webhook_deliveries.all()[:limit])
