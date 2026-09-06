"""M2: origen / adaptador de la bandeja (SFTP, carpeta, api_push)."""

from __future__ import annotations

import logging
import secrets
import socket

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

HELP = " Consulte la Ayuda para completar la información correctamente."
MSG_SAVED = "Origen guardado correctamente."
MSG_TEST_OK = (
    "Prueba simulada OK: host, puerto y credencial están. "
    "No se abrió sesión SFTP real en este MVP."
)
MSG_TEST_DNS = "No se pudo resolver el host. Revise el nombre o la IP."
MSG_ROTATED = "Token de push rotado. Cópielo ahora; no se volverá a mostrar completo."
MIN_POLL = 30


def snapshot_from_watch(watch: Watch) -> dict:
    return {
        "source_kind": watch.source_kind or Watch.SOURCE_SFTP,
        "filename_pattern": watch.filename_pattern or "*",
        "sftp_host": watch.sftp_host or "",
        "sftp_port": str(watch.sftp_port or 22),
        "sftp_username": watch.sftp_username or "",
        "sftp_secret": "",
        "sftp_secret_ref": watch.sftp_secret_ref or "",
        "sftp_remote_path": watch.sftp_remote_path or "",
        "poll_interval_sec": str(
            watch.poll_interval_sec
            or (60 if watch.source_kind == Watch.SOURCE_SFTP else 30)
        ),
        "after_detect": watch.after_detect or "",
        "folder_rel_path": watch.folder_rel_path
        or (f"watches/{watch.slug}/drop" if watch.slug else ""),
        "accept_multipart": "1" if watch.accept_multipart else "",
        "accept_storage_ref": "1" if watch.accept_storage_ref else "",
        "push_token_hint": watch.push_token_hint or "",
        "has_push_token": "1" if watch.push_token else "",
        "source_last_test_ok": watch.source_last_test_ok,
    }


def posted_from_request(post) -> dict:
    return {
        "source_kind": (post.get("source_kind") or "").strip(),
        "filename_pattern": (post.get("filename_pattern") or "").strip() or "*",
        "sftp_host": (post.get("sftp_host") or "").strip(),
        "sftp_port": (post.get("sftp_port") or "").strip(),
        "sftp_username": (post.get("sftp_username") or "").strip(),
        "sftp_secret": (post.get("sftp_secret") or "").strip(),
        "sftp_remote_path": (post.get("sftp_remote_path") or "").strip(),
        "poll_interval_sec": (post.get("poll_interval_sec") or "").strip(),
        "after_detect": (post.get("after_detect") or "").strip(),
        "folder_rel_path": (post.get("folder_rel_path") or "").strip(),
        "accept_multipart": str(post.get("accept_multipart") or ""),
        "accept_storage_ref": str(post.get("accept_storage_ref") or ""),
    }


def _truthy(value) -> bool:
    return str(value or "").lower() in {"1", "true", "on", "yes"}


def _parse_port(raw: str) -> int | None:
    try:
        port = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if port < 1 or port > 65535:
        return None
    return port


def _parse_poll(raw: str, default: int) -> int | None:
    try:
        val = int(str(raw).strip() or default)
    except (TypeError, ValueError):
        return None
    if val < MIN_POLL:
        return None
    return val


def update_source(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)

    kind = data.get("source_kind") or ""
    errors: dict[str, list[str]] = {}
    if kind not in {
        Watch.SOURCE_SFTP,
        Watch.SOURCE_MANAGED_FOLDER,
        Watch.SOURCE_API_PUSH,
    }:
        errors.setdefault("source_kind", []).append(
            "Seleccione un tipo de origen." + HELP
        )

    pattern = (data.get("filename_pattern") or "*").strip() or "*"
    if len(pattern) > 200:
        errors.setdefault("filename_pattern", []).append("Máximo 200 caracteres.")

    sftp_host = ""
    sftp_port = None
    sftp_username = ""
    sftp_secret_ref = watch.sftp_secret_ref or ""
    sftp_remote_path = ""
    poll = None
    after = ""
    folder = ""
    accept_multipart = True
    accept_storage_ref = False
    push_token = watch.push_token or ""
    push_hint = watch.push_token_hint or ""
    test_ok = watch.source_last_test_ok
    push_token_once = ""

    if kind == Watch.SOURCE_SFTP:
        sftp_host = (data.get("sftp_host") or "").strip()
        sftp_username = (data.get("sftp_username") or "").strip()
        sftp_remote_path = (data.get("sftp_remote_path") or "").strip()
        secret = (data.get("sftp_secret") or "").strip()
        sftp_port = _parse_port(data.get("sftp_port") or "22")
        poll = _parse_poll(data.get("poll_interval_sec") or "60", 60)
        after = (data.get("after_detect") or "").strip()
        if not sftp_host:
            errors.setdefault("sftp_host", []).append("Indique el host." + HELP)
        if sftp_port is None:
            errors.setdefault("sftp_port", []).append("Puerto inválido." + HELP)
        if not sftp_username:
            errors.setdefault("sftp_username", []).append("Indique el usuario." + HELP)
        if secret:
            sftp_secret_ref = f"secret:sftp:{watch.slug}:{secrets.token_hex(4)}"
        elif not sftp_secret_ref:
            errors.setdefault("sftp_secret", []).append(err.MESSAGES[err.SECRET_MISSING] + HELP)
            return OperationResult.failure(
                err.SECRET_MISSING,
                err.MESSAGES[err.SECRET_MISSING] + HELP,
                errors=errors,
            )
        if not sftp_remote_path:
            errors.setdefault("sftp_remote_path", []).append(
                "Indique la ruta remota." + HELP
            )
        if poll is None:
            errors.setdefault("poll_interval_sec", []).append(
                f"Mínimo {MIN_POLL} segundos." + HELP
            )
        if after not in {
            Watch.AFTER_LEAVE,
            Watch.AFTER_MARK,
            Watch.AFTER_DELETE_REMOTE,
        }:
            errors.setdefault("after_detect", []).append(
                "Elija qué hacer tras el intake." + HELP
            )
        if secret:
            test_ok = None

    elif kind == Watch.SOURCE_MANAGED_FOLDER:
        folder = (data.get("folder_rel_path") or "").strip() or f"watches/{watch.slug}/drop"
        if ".." in folder or folder.startswith("/") or "\\" in folder:
            errors.setdefault("folder_rel_path", []).append(
                "Use una ruta relativa al área de la compañía." + HELP
            )
        poll = _parse_poll(data.get("poll_interval_sec") or "30", 30)
        after = (data.get("after_detect") or "").strip()
        if poll is None:
            errors.setdefault("poll_interval_sec", []).append(
                f"Mínimo {MIN_POLL} segundos." + HELP
            )
        if after not in {
            Watch.AFTER_LEAVE,
            Watch.AFTER_MOVE_PROCESSED,
            Watch.AFTER_DELETE,
        }:
            errors.setdefault("after_detect", []).append(
                "Elija qué hacer tras el intake." + HELP
            )
        test_ok = None
        sftp_secret_ref = ""

    elif kind == Watch.SOURCE_API_PUSH:
        accept_multipart = _truthy(data.get("accept_multipart"))
        accept_storage_ref = _truthy(data.get("accept_storage_ref"))
        if not accept_multipart and not accept_storage_ref:
            accept_multipart = True
        if not push_token:
            push_token = secrets.token_urlsafe(32)
            push_hint = push_token[-4:]
            push_token_once = push_token
        after = Watch.AFTER_LEAVE
        poll = None
        test_ok = None
        sftp_secret_ref = ""

    if errors:
        return OperationResult.failure(
            err.SOURCE_INVALID if kind else err.VALIDATION_REQUIRED,
            err.MESSAGES[err.SOURCE_INVALID] if kind else MSG_VALIDATION,
            errors=errors,
        )

    try:
        with transaction.atomic():
            watch.source_kind = kind
            watch.filename_pattern = pattern
            watch.sftp_host = sftp_host
            watch.sftp_port = sftp_port
            watch.sftp_username = sftp_username
            watch.sftp_secret_ref = sftp_secret_ref
            watch.sftp_remote_path = sftp_remote_path
            watch.poll_interval_sec = poll
            watch.after_detect = after
            watch.folder_rel_path = folder
            watch.accept_multipart = accept_multipart
            watch.accept_storage_ref = accept_storage_ref
            watch.push_token = push_token
            watch.push_token_hint = push_hint
            watch.source_saved_at = timezone.now()
            watch.source_last_test_ok = test_ok
            watch.save(
                update_fields=[
                    "source_kind",
                    "filename_pattern",
                    "sftp_host",
                    "sftp_port",
                    "sftp_username",
                    "sftp_secret_ref",
                    "sftp_remote_path",
                    "poll_interval_sec",
                    "after_detect",
                    "folder_rel_path",
                    "accept_multipart",
                    "accept_storage_ref",
                    "push_token",
                    "push_token_hint",
                    "source_saved_at",
                    "source_last_test_ok",
                    "updated_at",
                ]
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_SOURCE_UPDATED,
                user,
                {
                    "source_kind": kind,
                    "filename_pattern": pattern,
                    "sftp_host": sftp_host,
                    "sftp_port": sftp_port,
                    "folder_rel_path": folder,
                    "after_detect": after,
                },
            )
    except Exception:
        logger.exception("update_source unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    payload = {"watch": watch}
    if push_token_once:
        payload["push_token_once"] = push_token_once
    return OperationResult.success(user_message=MSG_SAVED, payload=payload)


def test_sftp_connection(user, watch: Watch, data: dict | None = None) -> OperationResult:
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    data = data or {}
    host = (data.get("sftp_host") or watch.sftp_host or "").strip()
    port = _parse_port(data.get("sftp_port") or watch.sftp_port or 22)
    username = (data.get("sftp_username") or watch.sftp_username or "").strip()
    has_secret = bool(
        (data.get("sftp_secret") or "").strip() or watch.sftp_secret_ref
    )
    path = (data.get("sftp_remote_path") or watch.sftp_remote_path or "").strip()
    errors: dict[str, list[str]] = {}
    if not host:
        errors.setdefault("sftp_host", []).append("Indique el host.")
    if port is None:
        errors.setdefault("sftp_port", []).append("Puerto inválido.")
    if not username:
        errors.setdefault("sftp_username", []).append("Indique el usuario.")
    if not has_secret:
        errors.setdefault("sftp_secret", []).append(err.MESSAGES[err.SECRET_MISSING])
    if not path:
        errors.setdefault("sftp_remote_path", []).append("Indique la ruta remota.")
    if errors:
        return OperationResult.failure(
            err.SOURCE_INVALID,
            err.MESSAGES[err.SOURCE_INVALID],
            errors=errors,
        )

    ok = True
    message = MSG_TEST_OK
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        ok = False
        message = MSG_TEST_DNS
    except OSError:
        ok = True
        message = MSG_TEST_OK

    try:
        with transaction.atomic():
            watch.source_last_test_ok = ok
            watch.save(update_fields=["source_last_test_ok", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_SOURCE_TESTED,
                user,
                {"ok": ok, "sftp_host": host, "sftp_port": port},
            )
    except Exception:
        logger.exception("test_sftp unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    if not ok:
        return OperationResult.failure(err.SFTP_UNREACHABLE, message)
    return OperationResult.success(user_message=message, payload={"watch": watch})


def rotate_push_token(user, watch: Watch) -> OperationResult:
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if watch.source_kind != Watch.SOURCE_API_PUSH:
        return OperationResult.failure(
            err.SOURCE_INVALID, err.MESSAGES[err.SOURCE_INVALID]
        )
    token = secrets.token_urlsafe(32)
    try:
        with transaction.atomic():
            watch.push_token = token
            watch.push_token_hint = token[-4:]
            watch.save(update_fields=["push_token", "push_token_hint", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_PUSH_TOKEN_ROTATED,
                user,
                {"hint": watch.push_token_hint},
            )
    except Exception:
        logger.exception("rotate_push_token unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(
        user_message=MSG_ROTATED,
        payload={"watch": watch, "push_token_once": token},
    )
