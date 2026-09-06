"""M3: intake — política, storage, lote, hash."""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.services import storage_service
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

HELP = " Consulte la Ayuda para completar la información correctamente."
MSG_POLICY_SAVED = "Política de intake guardada."
STATUS_LABELS = dict(WatchBatch.STATUS_CHOICES)


def snapshot_policy(watch: Watch) -> dict:
    return {
        "settle_seconds": str(watch.settle_seconds),
        "max_bytes": str(watch.max_bytes),
        "pending_pick_policy": watch.pending_pick_policy or Watch.PICK_FIFO,
        "retain_consumed_days": str(watch.retain_consumed_days),
    }


def posted_policy(post) -> dict:
    return {
        "settle_seconds": (post.get("settle_seconds") or "").strip(),
        "max_bytes": (post.get("max_bytes") or "").strip(),
        "pending_pick_policy": (post.get("pending_pick_policy") or "").strip(),
        "retain_consumed_days": (post.get("retain_consumed_days") or "").strip(),
    }


def update_intake_policy(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)

    errors: dict[str, list[str]] = {}
    try:
        settle = int(data.get("settle_seconds") or 5)
        if settle < 0 or settle > 3600:
            raise ValueError
    except (TypeError, ValueError):
        settle = None
        errors.setdefault("settle_seconds", []).append("Indique segundos válidos (0–3600).")

    try:
        max_bytes = int(data.get("max_bytes") or 104857600)
        if max_bytes < 1:
            raise ValueError
    except (TypeError, ValueError):
        max_bytes = None
        errors.setdefault("max_bytes", []).append("Indique un tamaño máximo válido.")

    pick = data.get("pending_pick_policy") or ""
    if pick not in {Watch.PICK_FIFO, Watch.PICK_LIFO}:
        errors.setdefault("pending_pick_policy", []).append("Elija FIFO o LIFO.")

    try:
        retain = int(data.get("retain_consumed_days") or 90)
        if retain < 1 or retain > 3650:
            raise ValueError
    except (TypeError, ValueError):
        retain = None
        errors.setdefault("retain_consumed_days", []).append("Días de retención inválidos.")

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    try:
        with transaction.atomic():
            watch.settle_seconds = settle
            watch.max_bytes = max_bytes
            watch.pending_pick_policy = pick
            watch.retain_consumed_days = retain
            watch.intake_policy_saved_at = timezone.now()
            watch.save(
                update_fields=[
                    "settle_seconds",
                    "max_bytes",
                    "pending_pick_policy",
                    "retain_consumed_days",
                    "intake_policy_saved_at",
                    "updated_at",
                ]
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_INTAKE_POLICY_UPDATED,
                user,
                {
                    "settle_seconds": settle,
                    "max_bytes": max_bytes,
                    "pending_pick_policy": pick,
                    "retain_consumed_days": retain,
                },
            )
    except Exception:
        logger.exception("update_intake_policy unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(user_message=MSG_POLICY_SAVED, payload={"watch": watch})


def list_batches(watch: Watch, *, status: str = "") -> list[dict]:
    qs = WatchBatch.objects.filter(watch=watch).order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    rows = []
    for batch in qs[:500]:
        rows.append(
            {
                "batch": batch,
                "status_label": STATUS_LABELS.get(batch.status, batch.status),
                "hash_short": (batch.content_hash or "")[:12],
                "size_label": _size_label(batch.byte_size),
                "ingested_label": (
                    timezone.localtime(batch.ingested_at).strftime("%d/%m/%Y %H:%M")
                    if batch.ingested_at
                    else "—"
                ),
                "consumed_by": batch.consumed_by or "—",
            }
        )
    return rows


def _size_label(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n / (1024 * 1024):.1f} MiB"


def _batch_dir(company_id, watch_id, batch_id) -> Path:
    return (
        Path(settings.MEDIA_ROOT)
        / "watches"
        / str(company_id)
        / str(watch_id)
        / "batches"
        / str(batch_id)
    )


def _matches_pattern(filename: str, pattern: str) -> bool:
    pat = (pattern or "*").strip() or "*"
    return fnmatch.fnmatch(filename, pat)


def _quota_block(watch: Watch, byte_size: int) -> str | None:
    pending = WatchBatch.objects.filter(
        watch=watch, status=WatchBatch.STATUS_PENDING
    ).count()
    if watch.quota_max_pending and pending >= watch.quota_max_pending:
        return err.QUOTA_PENDING

    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = WatchBatch.objects.filter(watch=watch, created_at__gte=start).exclude(
        status=WatchBatch.STATUS_SKIPPED
    )
    if watch.quota_max_arrivals_per_day and today.count() >= watch.quota_max_arrivals_per_day:
        return err.QUOTA_DAILY
    if watch.quota_max_bytes_per_day:
        total = today.aggregate(s=Sum("byte_size"))["s"] or 0
        if total + byte_size > watch.quota_max_bytes_per_day:
            return err.QUOTA_BYTES
    return None


def _dup_existing(watch: Watch, content_hash: str) -> WatchBatch | None:
    window = timezone.now() - timedelta(days=watch.dup_window_days or 365)
    return (
        WatchBatch.objects.filter(
            watch=watch,
            content_hash=content_hash,
            created_at__gte=window,
        )
        .exclude(status=WatchBatch.STATUS_INTAKE_FAILED)
        .order_by("-created_at")
        .first()
    )


def ingest_bytes(
    watch: Watch,
    filename: str,
    data: bytes,
    source_kind: str = "",
) -> OperationResult:
    """Materializa bytes → storage + WatchBatch. Aplica idempotencia y cuotas."""
    if watch.status != Watch.STATUS_ACTIVE:
        return OperationResult.failure(err.INACTIVE, err.MESSAGES[err.INACTIVE])

    name = storage_service.sanitize_filename(filename or "file")
    if not _matches_pattern(name, watch.filename_pattern):
        return OperationResult.failure(
            err.SOURCE_INVALID,
            f"El nombre no coincide con el patrón {watch.filename_pattern}.",
        )

    raw = data if isinstance(data, (bytes, bytearray)) else bytes(data or b"")
    byte_size = len(raw)
    if watch.max_bytes and byte_size > watch.max_bytes:
        return _fail_batch(
            watch,
            name,
            source_kind,
            err.INTAKE_TOO_LARGE,
            byte_size=byte_size,
        )

    try:
        content_hash = hashlib.sha256(raw).hexdigest()
    except Exception:
        logger.exception("ingest hash failed watch=%s", watch.pk)
        return OperationResult.failure(
            err.INTAKE_HASH_FAILED, err.MESSAGES[err.INTAKE_HASH_FAILED]
        )

    existing = _dup_existing(watch, content_hash)
    if existing is not None:
        policy = watch.dup_policy or Watch.DUP_SKIP
        if policy == Watch.DUP_SKIP:
            skipped = WatchBatch.objects.create(
                company=watch.company,
                watch=watch,
                original_filename=name,
                content_hash=content_hash,
                byte_size=byte_size,
                status=WatchBatch.STATUS_SKIPPED,
                source_kind=source_kind or watch.source_kind,
                detected_at=timezone.now(),
                ingested_at=timezone.now(),
                error_code=err.DUPLICATE_CONTENT,
                correlation_id=str(uuid.uuid4())[:64],
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_BATCH_SKIPPED,
                None,
                {
                    "triggered_by": "system:file_watch",
                    "batch_id": str(skipped.id),
                    "error_code": err.DUPLICATE_CONTENT,
                    "filename": name,
                },
            )
            from apps.file_watch.services import watch_notify as notify_svc

            notify_svc.dispatch_for_batch(watch, skipped, kind="skip")
            return OperationResult.failure(
                err.DUPLICATE_CONTENT,
                err.MESSAGES[err.DUPLICATE_CONTENT],
                payload={"batch": skipped, "skipped": True},
            )
        if policy == Watch.DUP_REPLACE_PENDING and existing.status == WatchBatch.STATUS_PENDING:
            existing.status = WatchBatch.STATUS_SKIPPED
            existing.error_code = err.DUPLICATE_CONTENT
            existing.save(update_fields=["status", "error_code", "updated_at"])

    quota_code = _quota_block(watch, byte_size)
    if quota_code:
        skipped = WatchBatch.objects.create(
            company=watch.company,
            watch=watch,
            original_filename=name,
            content_hash=content_hash,
            byte_size=byte_size,
            status=WatchBatch.STATUS_SKIPPED,
            source_kind=source_kind or watch.source_kind,
            detected_at=timezone.now(),
            ingested_at=timezone.now(),
            error_code=quota_code,
            correlation_id=str(uuid.uuid4())[:64],
        )
        audit_svc.append_event(
            watch,
            WatchAuditEvent.EVENT_BATCH_SKIPPED,
            None,
            {
                "triggered_by": "system:file_watch",
                "batch_id": str(skipped.id),
                "error_code": quota_code,
                "filename": name,
            },
        )
        from apps.file_watch.services import watch_notify as notify_svc

        notify_svc.dispatch_for_batch(watch, skipped, kind="skip")
        return OperationResult.failure(
            quota_code,
            err.MESSAGES[quota_code],
            payload={"batch": skipped, "skipped": True},
        )

    batch_id = uuid.uuid4()
    dest = _batch_dir(watch.company_id, watch.id, batch_id)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        absolute = dest / name
        absolute.write_bytes(raw)
        stored_path = storage_service.relative_to_media(absolute)
    except Exception:
        logger.exception("ingest store failed watch=%s", watch.pk)
        return _fail_batch(
            watch,
            name,
            source_kind,
            err.INTAKE_STORE_FAILED,
            byte_size=byte_size,
            content_hash=content_hash,
        )

    now = timezone.now()
    batch = WatchBatch.objects.create(
        id=batch_id,
        company=watch.company,
        watch=watch,
        original_filename=name,
        content_hash=content_hash,
        storage_key=stored_path,
        byte_size=byte_size,
        status=WatchBatch.STATUS_PENDING,
        source_kind=source_kind or watch.source_kind,
        detected_at=now,
        ingested_at=now,
        correlation_id=str(uuid.uuid4())[:64],
    )
    audit_svc.append_event(
        watch,
        WatchAuditEvent.EVENT_BATCH_INGESTED,
        None,
        {
            "triggered_by": "system:file_watch",
            "batch_id": str(batch.id),
            "filename": name,
            "content_hash": content_hash,
            "byte_size": byte_size,
        },
    )

    if watch.fire_mode == Watch.FIRE_ON_ARRIVAL:
        from apps.file_watch.services import watch_fire as fire_svc

        fire_svc.try_fire_on_arrival(watch, batch)
        batch.refresh_from_db()

    return OperationResult.success(
        user_message="Lote ingerido.",
        payload={"batch": batch},
    )


def _fail_batch(
    watch: Watch,
    filename: str,
    source_kind: str,
    error_code: str,
    *,
    byte_size: int = 0,
    content_hash: str = "",
) -> OperationResult:
    batch = WatchBatch.objects.create(
        company=watch.company,
        watch=watch,
        original_filename=filename,
        content_hash=content_hash,
        byte_size=byte_size,
        status=WatchBatch.STATUS_INTAKE_FAILED,
        source_kind=source_kind or watch.source_kind,
        detected_at=timezone.now(),
        error_code=error_code,
        correlation_id=str(uuid.uuid4())[:64],
    )
    audit_svc.append_event(
        watch,
        WatchAuditEvent.EVENT_BATCH_INTAKE_FAILED,
        None,
        {
            "triggered_by": "system:file_watch",
            "batch_id": str(batch.id),
            "error_code": error_code,
            "filename": filename,
        },
    )
    from apps.file_watch.services import watch_notify as notify_svc

    notify_svc.dispatch_for_batch(watch, batch, kind="intake_failed")
    return OperationResult.failure(
        error_code,
        err.MESSAGES.get(error_code, err.MESSAGES[err.INTAKE_STORE_FAILED]),
        payload={"batch": batch},
    )


def drop_folder_absolute(watch: Watch) -> Path:
    rel = (watch.folder_rel_path or f"watches/{watch.slug}/drop").strip().replace("\\", "/")
    root = Path(settings.MEDIA_ROOT) / "watches" / str(watch.company_id)
    # folder_rel_path may already start with watches/{slug}/drop
    if rel.startswith("watches/"):
        path = Path(settings.MEDIA_ROOT) / rel
    else:
        path = root / rel
    # Jail: must stay under company watches prefix
    company_root = (Path(settings.MEDIA_ROOT) / "watches" / str(watch.company_id)).resolve()
    try:
        path.resolve().relative_to(company_root)
    except ValueError:
        path = company_root / "drop" / watch.slug
    return path


def scan_managed_folder(watch: Watch) -> dict:
    """Escanea carpeta drop e ingiere archivos nuevos que cumplan el patrón."""
    stats = {"seen": 0, "ingested": 0, "skipped": 0, "failed": 0}
    if watch.source_kind != Watch.SOURCE_MANAGED_FOLDER:
        return stats
    if watch.status != Watch.STATUS_ACTIVE:
        return stats
    folder = drop_folder_absolute(watch)
    folder.mkdir(parents=True, exist_ok=True)
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        stats["seen"] += 1
        try:
            data = path.read_bytes()
        except OSError:
            stats["failed"] += 1
            continue
        result = ingest_bytes(
            watch, path.name, data, source_kind=Watch.SOURCE_MANAGED_FOLDER
        )
        if result.ok:
            stats["ingested"] += 1
            if watch.after_detect == Watch.AFTER_LEAVE and path.is_file():
                # already copied to batch storage; leave original
                pass
            elif watch.after_detect == Watch.AFTER_DELETE and path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
            elif watch.after_detect == Watch.AFTER_MOVE_PROCESSED and path.is_file():
                processed = folder.parent / "processed"
                processed.mkdir(parents=True, exist_ok=True)
                try:
                    path.replace(processed / path.name)
                except OSError:
                    pass
        elif (result.payload or {}).get("skipped"):
            stats["skipped"] += 1
        else:
            stats["failed"] += 1
    return stats


def process_active_managed_watches() -> dict:
    total = {"watches": 0, "ingested": 0, "skipped": 0, "failed": 0}
    qs = Watch.objects.filter(
        status=Watch.STATUS_ACTIVE,
        source_kind=Watch.SOURCE_MANAGED_FOLDER,
    ).exclude(source_saved_at__isnull=True)
    for watch in qs:
        total["watches"] += 1
        stats = scan_managed_folder(watch)
        total["ingested"] += stats["ingested"]
        total["skipped"] += stats["skipped"]
        total["failed"] += stats["failed"]
    return total
