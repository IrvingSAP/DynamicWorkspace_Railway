"""M9: correo Resend y webhook HTTPS al fallar intake / fire / run / skip."""

from __future__ import annotations

import json
import logging
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.services.email_delivery import send_email
from apps.core.services.operation_result import OperationResult
from apps.file_watch.models import (
    Watch,
    WatchAuditEvent,
    WatchBatch,
    WatchMembership,
    WatchNotifyDispatch,
)
from apps.file_watch.services import watch_audit as audit_svc
from apps.file_watch.services import watch_errors as err
from apps.file_watch.services.watch_lifecycle_service import (
    MSG_FORBIDDEN,
    MSG_UNEXPECTED,
    user_can_edit,
)
from apps.platform_api.services.webhook_service import (
    EVENT_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    sign_payload,
)

logger = logging.getLogger(__name__)

MSG_SAVED = err.MSG_NOTIFY_SAVED
MSG_NEED_DEST = "Marque al menos un miembro de la bandeja o indique un webhook HTTPS."
MSG_WEBHOOK_HTTPS = err.MESSAGES[err.NOTIFY_WEBHOOK_INVALID]
HELP = " Consulte la Ayuda para completar la información correctamente."
POST_TIMEOUT = 8


def snapshot_from_watch(watch: Watch) -> dict:
    ids = [str(x) for x in (watch.notify_user_ids or [])]
    return {
        "notify_enabled": "1" if watch.notify_enabled else "",
        "notify_on_intake_failed": "1" if watch.notify_on_intake_failed else "",
        "notify_on_fire_failed": "1" if watch.notify_on_fire_failed else "",
        "notify_on_run_failed": "1" if watch.notify_on_run_failed else "",
        "notify_on_skip": "1" if watch.notify_on_skip else "",
        "notify_user_ids": ids,
        "notify_webhook_url": watch.notify_webhook_url or "",
    }


def posted_from_request(post) -> dict:
    raw_ids = post.getlist("notify_user") if hasattr(post, "getlist") else []
    return {
        "notify_enabled": str(post.get("notify_enabled") or ""),
        "notify_on_intake_failed": str(post.get("notify_on_intake_failed") or ""),
        "notify_on_fire_failed": str(post.get("notify_on_fire_failed") or ""),
        "notify_on_run_failed": str(post.get("notify_on_run_failed") or ""),
        "notify_on_skip": str(post.get("notify_on_skip") or ""),
        "notify_user_ids": [str(x).strip() for x in raw_ids if str(x).strip()],
        "notify_webhook_url": (post.get("notify_webhook_url") or "").strip(),
    }


def _truthy(value) -> bool:
    return str(value or "").lower() in {"1", "true", "on", "yes"}


def _webhook_ok(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname)


def _channel(user_ids: list[str], webhook_url: str) -> str:
    has_mail = bool(user_ids)
    has_hook = bool(webhook_url)
    if has_mail and has_hook:
        return Watch.CHANNEL_BOTH
    if has_hook:
        return Watch.CHANNEL_WEBHOOK
    return Watch.CHANNEL_EMAIL


def member_choices(watch: Watch) -> list[dict]:
    rows = []
    memberships = (
        WatchMembership.objects.filter(watch=watch, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    for item in memberships:
        user = item.user
        rows.append(
            {
                "id": str(user.id),
                "username": user.username,
                "email": (user.email or "").strip(),
                "role": item.role,
                "label": user.get_full_name() or user.username,
            }
        )
    return rows


def save_notify(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)

    enabled = _truthy(data.get("notify_enabled"))
    on_intake = _truthy(data.get("notify_on_intake_failed")) if enabled else True
    on_fire = _truthy(data.get("notify_on_fire_failed")) if enabled else True
    on_run = _truthy(data.get("notify_on_run_failed")) if enabled else True
    on_skip = _truthy(data.get("notify_on_skip")) if enabled else False
    if enabled and not on_intake and not on_fire and not on_run and not on_skip:
        on_intake = True
        on_fire = True

    allowed_rows = member_choices(watch)
    allowed = {str(row["id"]) for row in allowed_rows}
    user_ids = [uid for uid in (data.get("notify_user_ids") or []) if uid in allowed]
    webhook_url = (data.get("notify_webhook_url") or "").strip()

    errors: dict[str, list[str]] = {}
    if enabled:
        if webhook_url and not _webhook_ok(webhook_url):
            errors.setdefault("notify_webhook_url", []).append(MSG_WEBHOOK_HTTPS + HELP)
            return OperationResult.failure(
                err.NOTIFY_WEBHOOK_INVALID,
                MSG_WEBHOOK_HTTPS + HELP,
                errors=errors,
            )
        if not user_ids and not webhook_url:
            errors.setdefault("notify_user_ids", []).append(MSG_NEED_DEST + HELP)
            return OperationResult.failure(
                err.VALIDATION_REQUIRED,
                MSG_NEED_DEST + HELP,
                errors=errors,
            )
        emails_by_id = {row["id"]: row["email"] for row in allowed_rows}
        if any(not emails_by_id.get(uid) for uid in user_ids):
            return OperationResult.failure(
                err.NOTIFY_EMAIL_INVALID,
                err.MESSAGES[err.NOTIFY_EMAIL_INVALID] + HELP,
                errors={
                    "notify_user_ids": [err.MESSAGES[err.NOTIFY_EMAIL_INVALID]]
                },
            )

    secret = watch.notify_webhook_secret or ""
    if enabled and webhook_url:
        if webhook_url != (watch.notify_webhook_url or "") or not secret:
            secret = secrets.token_urlsafe(32)
    if not webhook_url:
        secret = ""

    channel = _channel(user_ids, webhook_url) if enabled else ""
    try:
        with transaction.atomic():
            watch.notify_enabled = enabled
            watch.notify_on_intake_failed = on_intake
            watch.notify_on_fire_failed = on_fire
            watch.notify_on_run_failed = on_run
            watch.notify_on_skip = on_skip
            watch.notify_channel = channel
            watch.notify_user_ids = user_ids
            watch.notify_webhook_url = webhook_url
            watch.notify_webhook_secret = secret
            watch.notify_saved_at = timezone.now()
            watch.save(
                update_fields=[
                    "notify_enabled",
                    "notify_on_intake_failed",
                    "notify_on_fire_failed",
                    "notify_on_run_failed",
                    "notify_on_skip",
                    "notify_channel",
                    "notify_user_ids",
                    "notify_webhook_url",
                    "notify_webhook_secret",
                    "notify_saved_at",
                    "updated_at",
                ]
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_NOTIFY_UPDATED,
                user,
                {
                    "notify_enabled": enabled,
                    "notify_channel": channel,
                    "notify_on_intake_failed": on_intake,
                    "notify_on_fire_failed": on_fire,
                    "notify_on_run_failed": on_run,
                    "notify_on_skip": on_skip,
                },
            )
    except Exception:
        logger.exception("save_notify unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_SAVED, payload={"watch": watch})


def dispatch_for_batch(watch: Watch, batch: WatchBatch, *, kind: str) -> None:
    kind_map = {
        "intake_failed": WatchNotifyDispatch.KIND_INTAKE_FAILED,
        "fire_failed": WatchNotifyDispatch.KIND_FIRE_FAILED,
        "run_failed": WatchNotifyDispatch.KIND_RUN_FAILED,
        "skip": WatchNotifyDispatch.KIND_SKIP,
    }
    dispatch_kind = kind_map.get(kind)
    if not dispatch_kind:
        return
    event = {
        WatchNotifyDispatch.KIND_INTAKE_FAILED: "watch.intake_failed",
        WatchNotifyDispatch.KIND_FIRE_FAILED: "watch.fire_failed",
        WatchNotifyDispatch.KIND_RUN_FAILED: "watch.run_failed",
        WatchNotifyDispatch.KIND_SKIP: "watch.batch_skipped",
    }[dispatch_kind]
    _dispatch(watch, dispatch_kind, str(batch.id), event=event, batch=batch)


def _should_send(watch: Watch, kind: str) -> bool:
    if not watch.notify_enabled:
        return False
    if kind == WatchNotifyDispatch.KIND_INTAKE_FAILED:
        return bool(watch.notify_on_intake_failed)
    if kind == WatchNotifyDispatch.KIND_FIRE_FAILED:
        return bool(watch.notify_on_fire_failed)
    if kind == WatchNotifyDispatch.KIND_RUN_FAILED:
        return bool(watch.notify_on_run_failed)
    if kind == WatchNotifyDispatch.KIND_SKIP:
        return bool(watch.notify_on_skip)
    return False


def _claim(watch: Watch, kind: str, ref_id: str) -> bool:
    try:
        with transaction.atomic():
            WatchNotifyDispatch.objects.create(
                watch=watch, kind=kind, ref_id=ref_id[:64]
            )
        return True
    except IntegrityError:
        return False


def _dispatch(
    watch: Watch,
    kind: str,
    ref_id: str,
    *,
    event: str,
    batch: WatchBatch | None,
) -> None:
    if not _should_send(watch, kind):
        return
    if not _claim(watch, kind, ref_id):
        return
    error_code = (batch.error_code if batch else "") or ""
    occurred = timezone.now()
    email_ok = None
    hook_ok = None
    channel = watch.notify_channel
    if channel in {Watch.CHANNEL_EMAIL, Watch.CHANNEL_BOTH}:
        email_ok = _send_mail(watch, event, batch, error_code)
    if channel in {Watch.CHANNEL_WEBHOOK, Watch.CHANNEL_BOTH}:
        hook_ok = _post_webhook(watch, event, occurred, batch, error_code)
    result = "ok"
    if email_ok is False or hook_ok is False:
        result = "failed"
    audit_svc.append_event(
        watch,
        WatchAuditEvent.EVENT_NOTIFY_SENT,
        None,
        {
            "triggered_by": "system:file_watch",
            "channel": channel,
            "kind": kind,
            "result": result,
            "email_ok": email_ok,
            "webhook_ok": hook_ok,
            "error_code": error_code,
            "batch_id": str(batch.id) if batch else "",
        },
    )


def _send_mail(
    watch: Watch,
    event: str,
    batch: WatchBatch | None,
    error_code: str,
) -> bool:
    allowed = {str(x) for x in (watch.notify_user_ids or [])}
    recipients = []
    for row in member_choices(watch):
        if row["id"] in allowed and row["email"]:
            recipients.append(row["email"])
    if not recipients:
        return False
    detail = err.message_for(error_code) or error_code or "Aviso de File Watch"
    body = "\n".join(
        [
            f"Bandeja: {watch.slug}",
            f"Evento: {event}",
            f"Detalle: {detail}",
            f"batch_id: {batch.id if batch else '—'}",
            f"archivo: {(batch.original_filename if batch else '') or '—'}",
        ]
    )
    result = send_email(
        to=recipients,
        subject=f"[File Watch] {watch.slug} — aviso",
        body=body,
    )
    if not result.ok:
        logger.error("watch notify email failed slug=%s", watch.slug)
        return False
    return True


def _post_webhook(
    watch: Watch,
    event: str,
    occurred,
    batch: WatchBatch | None,
    error_code: str,
) -> bool:
    url = (watch.notify_webhook_url or "").strip()
    secret = watch.notify_webhook_secret or ""
    if not url or not secret:
        return False
    payload = {
        "watch_id": str(watch.id),
        "watch_slug": watch.slug,
        "event": event,
        "occurred_at": occurred.isoformat(),
        "batch_id": str(batch.id) if batch else None,
        "error_code": error_code or None,
    }
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(occurred.timestamp()))
    headers = {
        "Content-Type": "application/json",
        EVENT_HEADER: event,
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: sign_payload(secret, body),
        "User-Agent": "DynamicWorkspace-FileWatch/1.0",
    }
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=POST_TIMEOUT) as response:
            code = int(getattr(response, "status", 200) or 200)
        return 200 <= code < 300
    except HTTPError as exc:
        logger.exception("watch webhook HTTP slug=%s code=%s", watch.slug, exc.code)
        return False
    except (URLError, TimeoutError, OSError):
        logger.exception("watch webhook failed slug=%s", watch.slug)
        return False
