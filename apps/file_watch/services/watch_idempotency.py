"""M6: idempotencia — duplicados, reintentos, cuotas."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.file_watch.models import Watch, WatchAuditEvent
from apps.file_watch.services import watch_audit as audit_svc
from apps.file_watch.services import watch_errors as err
from apps.file_watch.services.watch_lifecycle_service import (
    MSG_FORBIDDEN,
    MSG_UNEXPECTED,
    MSG_VALIDATION,
    user_can_edit,
)

logger = logging.getLogger(__name__)

MSG_SAVED = "Idempotencia guardada correctamente."


def snapshot_from_watch(watch: Watch) -> dict:
    return {
        "dup_policy": watch.dup_policy or Watch.DUP_SKIP,
        "dup_window_days": str(watch.dup_window_days),
        "retry_max": str(watch.retry_max),
        "retry_backoff_sec": str(watch.retry_backoff_sec),
        "quota_max_pending": str(watch.quota_max_pending),
        "quota_max_arrivals_per_day": str(watch.quota_max_arrivals_per_day),
        "quota_max_bytes_per_day": str(watch.quota_max_bytes_per_day),
    }


def posted_from_request(post) -> dict:
    return {
        "dup_policy": (post.get("dup_policy") or "").strip(),
        "dup_window_days": (post.get("dup_window_days") or "").strip(),
        "retry_max": (post.get("retry_max") or "").strip(),
        "retry_backoff_sec": (post.get("retry_backoff_sec") or "").strip(),
        "quota_max_pending": (post.get("quota_max_pending") or "").strip(),
        "quota_max_arrivals_per_day": (post.get("quota_max_arrivals_per_day") or "").strip(),
        "quota_max_bytes_per_day": (post.get("quota_max_bytes_per_day") or "").strip(),
    }


def _int_field(raw, *, default: int, min_v: int = 0, max_v: int = 10_000_000) -> int | None:
    try:
        val = int(str(raw).strip() if raw not in (None, "") else default)
    except (TypeError, ValueError):
        return None
    if val < min_v or val > max_v:
        return None
    return val


def save_idempotency(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)

    errors: dict[str, list[str]] = {}
    dup = data.get("dup_policy") or ""
    if dup not in {Watch.DUP_SKIP, Watch.DUP_ALLOW, Watch.DUP_REPLACE_PENDING}:
        errors.setdefault("dup_policy", []).append("Seleccione una política de duplicados.")

    window = _int_field(data.get("dup_window_days"), default=365, min_v=1, max_v=3650)
    if window is None:
        errors.setdefault("dup_window_days", []).append("Ventana en días inválida.")

    retry_max = _int_field(data.get("retry_max"), default=3, min_v=0, max_v=20)
    if retry_max is None:
        errors.setdefault("retry_max", []).append("Reintentos inválidos.")

    backoff = _int_field(data.get("retry_backoff_sec"), default=60, min_v=1, max_v=86400)
    if backoff is None:
        errors.setdefault("retry_backoff_sec", []).append("Backoff inválido.")

    max_pending = _int_field(data.get("quota_max_pending"), default=50, min_v=1, max_v=10000)
    if max_pending is None:
        errors.setdefault("quota_max_pending", []).append("Cuota de pendientes inválida.")

    max_day = _int_field(
        data.get("quota_max_arrivals_per_day"), default=200, min_v=1, max_v=100000
    )
    if max_day is None:
        errors.setdefault("quota_max_arrivals_per_day", []).append(
            "Cuota diaria de llegadas inválida."
        )

    max_bytes = _int_field(
        data.get("quota_max_bytes_per_day"), default=0, min_v=0, max_v=10**15
    )
    if max_bytes is None:
        errors.setdefault("quota_max_bytes_per_day", []).append(
            "Cuota de bytes diarios inválida."
        )

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    try:
        with transaction.atomic():
            watch.dup_policy = dup
            watch.dup_window_days = window
            watch.retry_max = retry_max
            watch.retry_backoff_sec = backoff
            watch.quota_max_pending = max_pending
            watch.quota_max_arrivals_per_day = max_day
            watch.quota_max_bytes_per_day = max_bytes
            watch.idempotency_saved_at = timezone.now()
            watch.save(
                update_fields=[
                    "dup_policy",
                    "dup_window_days",
                    "retry_max",
                    "retry_backoff_sec",
                    "quota_max_pending",
                    "quota_max_arrivals_per_day",
                    "quota_max_bytes_per_day",
                    "idempotency_saved_at",
                    "updated_at",
                ]
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_IDEMPOTENCY_UPDATED,
                user,
                {
                    "dup_policy": dup,
                    "dup_window_days": window,
                    "retry_max": retry_max,
                    "quota_max_pending": max_pending,
                },
            )
    except Exception:
        logger.exception("save_idempotency unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(user_message=MSG_SAVED, payload={"watch": watch})
