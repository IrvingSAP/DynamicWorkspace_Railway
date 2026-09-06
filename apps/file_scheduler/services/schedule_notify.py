"""M9: correo Resend y webhook HTTPS al fallar tick o run delegado."""

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
from apps.file_scheduler.models import (
    Schedule,
    ScheduleAuditEvent,
    ScheduleMembership,
    ScheduleNotifyDispatch,
    ScheduleTick,
)
from apps.file_scheduler.services import schedule_errors as err
from apps.file_scheduler.services.schedule_lifecycle_service import (
    MSG_FORBIDDEN,
    MSG_UNEXPECTED,
    _record_event,
    user_can_edit,
)
from apps.platform_api.services.webhook_service import (
    EVENT_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    sign_payload,
)

logger = logging.getLogger(__name__)

MSG_SAVED = "Avisos guardados."
MSG_FORBIDDEN_SAVE = "No tiene permiso para editar los avisos de este plan."
MSG_NEED_DEST = (
    "Marque al menos un miembro del plan o indique un webhook HTTPS."
)
MSG_WEBHOOK_HTTPS = "El webhook debe empezar por https://."
HELP = " Consulte la Ayuda para completar la información correctamente."

POST_TIMEOUT = 8


def snapshot_from_schedule(schedule: Schedule) -> dict:
    ids = [str(x) for x in (schedule.notify_user_ids or [])]
    return {
        "notify_enabled": "1" if schedule.notify_enabled else "",
        "notify_on_tick_failed": "1" if schedule.notify_on_tick_failed else "",
        "notify_on_run_failed": "1" if schedule.notify_on_run_failed else "",
        "notify_on_skip": "1" if schedule.notify_on_skip else "",
        "notify_user_ids": ids,
        "notify_webhook_url": schedule.notify_webhook_url or "",
    }


def posted_from_request(post) -> dict:
    raw_ids = post.getlist("notify_user") if hasattr(post, "getlist") else []
    return {
        "notify_enabled": str(post.get("notify_enabled") or ""),
        "notify_on_tick_failed": str(post.get("notify_on_tick_failed") or ""),
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
        return Schedule.CHANNEL_BOTH
    if has_hook:
        return Schedule.CHANNEL_WEBHOOK
    return Schedule.CHANNEL_EMAIL


def member_choices(schedule: Schedule) -> list[dict]:
    rows = []
    memberships = (
        ScheduleMembership.objects.filter(schedule=schedule, is_active=True)
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


def save_notify(user, schedule: Schedule, data: dict) -> OperationResult:
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN_SAVE)

    enabled = _truthy(data.get("notify_enabled"))
    on_tick = _truthy(data.get("notify_on_tick_failed")) if enabled else True
    on_run = _truthy(data.get("notify_on_run_failed")) if enabled else True
    on_skip = _truthy(data.get("notify_on_skip")) if enabled else False
    if enabled and not on_tick and not on_run and not on_skip:
        on_tick = True
        on_run = True

    allowed_rows = member_choices(schedule)
    allowed = {str(row["id"]) for row in allowed_rows}
    user_ids = [uid for uid in (data.get("notify_user_ids") or []) if uid in allowed]
    webhook_url = (data.get("notify_webhook_url") or "").strip()

    errors: dict[str, list[str]] = {}
    if enabled:
        if webhook_url and not _webhook_ok(webhook_url):
            errors.setdefault("notify_webhook_url", []).append(MSG_WEBHOOK_HTTPS + HELP)
            return OperationResult.failure(
                "schedule_notify_webhook_invalid",
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
                "schedule_notify_email_invalid",
                "Un miembro marcado no tiene correo en su cuenta." + HELP,
                errors={
                    "notify_user_ids": ["Un miembro marcado no tiene correo en su cuenta."]
                },
            )

    secret = schedule.notify_webhook_secret or ""
    if enabled and webhook_url:
        if webhook_url != (schedule.notify_webhook_url or "") or not secret:
            secret = secrets.token_urlsafe(32)
    if not webhook_url:
        secret = ""

    channel = _channel(user_ids, webhook_url) if enabled else ""
    previous_status = schedule.status
    try:
        with transaction.atomic():
            schedule.notify_enabled = enabled
            schedule.notify_on_tick_failed = on_tick
            schedule.notify_on_run_failed = on_run
            schedule.notify_on_skip = on_skip
            schedule.notify_channel = channel
            schedule.notify_user_ids = user_ids
            schedule.notify_webhook_url = webhook_url
            schedule.notify_webhook_secret = secret
            schedule.notify_saved_at = timezone.now()
            schedule.save(
                update_fields=[
                    "notify_enabled",
                    "notify_on_tick_failed",
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
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {
                    "notify_enabled": enabled,
                    "notify_channel": channel,
                    "notify_on_tick_failed": on_tick,
                    "notify_on_run_failed": on_run,
                    "notify_on_skip": on_skip,
                    "status_unchanged": previous_status,
                },
            )
    except Exception:
        logger.exception("save_notify unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_SAVED, payload={"schedule": schedule})


def dispatch_for_tick(tick: ScheduleTick) -> None:
    schedule = tick.schedule
    if tick.status == ScheduleTick.STATUS_FAILED:
        _dispatch(
            schedule,
            ScheduleNotifyDispatch.KIND_TICK_FAILED,
            str(tick.id),
            event="schedule.tick_failed",
            tick=tick,
        )
    elif tick.status == ScheduleTick.STATUS_SKIPPED:
        _dispatch(
            schedule,
            ScheduleNotifyDispatch.KIND_TICK_SKIPPED,
            str(tick.id),
            event="schedule.tick_skipped",
            tick=tick,
        )


def dispatch_for_job(job) -> None:
    if getattr(job, "status", "") != "failed":
        return
    tick = (
        ScheduleTick.objects.select_related("schedule")
        .filter(job_id=str(job.id))
        .first()
    )
    if tick is None:
        return
    _dispatch(
        tick.schedule,
        ScheduleNotifyDispatch.KIND_RUN_FAILED,
        f"job:{job.id}",
        event="schedule.run_failed",
        tick=tick,
        job_id=str(job.id),
    )


def dispatch_for_pipeline(run) -> None:
    from apps.file_pipeline.models import PipelineRun

    if run.status != PipelineRun.STATUS_FAILED:
        return
    tick = (
        ScheduleTick.objects.select_related("schedule")
        .filter(pipeline_run_id=str(run.id))
        .first()
    )
    schedule = None
    if tick is not None:
        schedule = tick.schedule
    elif run.schedule_id:
        schedule = Schedule.objects.filter(pk=run.schedule_id).first()
    if schedule is None:
        return
    _dispatch(
        schedule,
        ScheduleNotifyDispatch.KIND_RUN_FAILED,
        f"pipeline:{run.id}",
        event="schedule.run_failed",
        tick=tick,
        pipeline_run_id=str(run.id),
    )


def _should_send(schedule: Schedule, kind: str) -> bool:
    if not schedule.notify_enabled:
        return False
    if kind == ScheduleNotifyDispatch.KIND_TICK_FAILED:
        return bool(schedule.notify_on_tick_failed)
    if kind == ScheduleNotifyDispatch.KIND_TICK_SKIPPED:
        return bool(schedule.notify_on_skip)
    if kind == ScheduleNotifyDispatch.KIND_RUN_FAILED:
        return bool(schedule.notify_on_run_failed)
    return False


def _claim(schedule: Schedule, kind: str, ref_id: str) -> bool:
    try:
        with transaction.atomic():
            ScheduleNotifyDispatch.objects.create(
                schedule=schedule, kind=kind, ref_id=ref_id[:64]
            )
        return True
    except IntegrityError:
        return False


def _dispatch(
    schedule: Schedule,
    kind: str,
    ref_id: str,
    *,
    event: str,
    tick: ScheduleTick | None,
    job_id: str = "",
    pipeline_run_id: str = "",
) -> None:
    if not _should_send(schedule, kind):
        return
    if not _claim(schedule, kind, ref_id):
        return
    job_id = job_id or (tick.job_id if tick else "")
    pipeline_run_id = pipeline_run_id or (tick.pipeline_run_id if tick else "")
    error_code = (tick.error_code if tick else "") or ""
    occurred = timezone.now()
    email_ok = None
    hook_ok = None
    channel = schedule.notify_channel
    if channel in {Schedule.CHANNEL_EMAIL, Schedule.CHANNEL_BOTH}:
        email_ok = _send_mail(schedule, event, tick, job_id, pipeline_run_id, error_code)
    if channel in {Schedule.CHANNEL_WEBHOOK, Schedule.CHANNEL_BOTH}:
        hook_ok = _post_webhook(
            schedule,
            event,
            occurred,
            tick,
            job_id,
            pipeline_run_id,
            error_code,
        )
    result = "ok"
    if email_ok is False or hook_ok is False:
        result = "failed"
    _record_event(
        schedule,
        ScheduleAuditEvent.EVENT_NOTIFY_SENT,
        None,
        {
            "triggered_by": "system:scheduler",
            "channel": channel,
            "kind": kind,
            "result": result,
            "email_ok": email_ok,
            "webhook_ok": hook_ok,
            "error_code": error_code,
            "job_id": job_id,
            "pipeline_run_id": pipeline_run_id,
            "tick_id": str(tick.id) if tick else "",
        },
    )


def _send_mail(
    schedule: Schedule,
    event: str,
    tick: ScheduleTick | None,
    job_id: str,
    pipeline_run_id: str,
    error_code: str,
) -> bool:
    allowed = {str(x) for x in (schedule.notify_user_ids or [])}
    recipients = []
    for row in member_choices(schedule):
        if row["id"] in allowed and row["email"]:
            recipients.append(row["email"])
    if not recipients:
        return False
    window = ""
    if tick is not None:
        window = timezone.localtime(tick.scheduled_for).strftime("%Y-%m-%d %H:%M")
    if event == "schedule.run_failed":
        detail = "El Job o pipeline falló. Abra el run enlazado; no se incluye el archivo."
    else:
        detail = error_code or "El programador no pudo encolar."
    body = "\n".join(
        [
            f"Plan: {schedule.slug}",
            f"Evento: {event}",
            f"Ventana: {window or '—'}",
            f"Detalle: {detail}",
            f"job_id: {job_id or '—'}",
            f"pipeline_run_id: {pipeline_run_id or '—'}",
        ]
    )
    result = send_email(
        to=recipients,
        subject=f"[File Scheduler] {schedule.slug} — aviso",
        body=body,
    )
    if not result.ok:
        logger.error("schedule notify email failed slug=%s", schedule.slug)
        return False
    return True


def _post_webhook(
    schedule: Schedule,
    event: str,
    occurred,
    tick: ScheduleTick | None,
    job_id: str,
    pipeline_run_id: str,
    error_code: str,
) -> bool:
    url = (schedule.notify_webhook_url or "").strip()
    secret = schedule.notify_webhook_secret or ""
    if not url or not secret:
        return False
    payload = {
        "schedule_id": str(schedule.id),
        "event": event,
        "occurred_at": occurred.isoformat(),
        "job_id": job_id or None,
        "pipeline_run_id": pipeline_run_id or None,
        "error_code": error_code or None,
        "tick_id": str(tick.id) if tick else None,
    }
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(occurred.timestamp()))
    headers = {
        "Content-Type": "application/json",
        EVENT_HEADER: event,
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: sign_payload(secret, body),
        "User-Agent": "DynamicWorkspace-FileScheduler/1.0",
    }
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=POST_TIMEOUT) as response:
            code = int(getattr(response, "status", 200) or 200)
        return 200 <= code < 300
    except HTTPError as exc:
        logger.exception("schedule webhook HTTP slug=%s code=%s", schedule.slug, exc.code)
        return False
    except (URLError, TimeoutError, OSError):
        logger.exception("schedule webhook failed slug=%s", schedule.slug)
        return False
