"""M10: claim atómico de lote pending (Scheduler / fire / API)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.file_watch.models import Watch, WatchAuditEvent, WatchBatch
from apps.file_watch.services import watch_audit as audit_svc


def get_watch_by_slug(company, slug: str) -> Watch | None:
    slug = (slug or "").strip()
    if not slug:
        return None
    return (
        Watch.objects.filter(company=company, slug=slug)
        .exclude(status=Watch.STATUS_ARCHIVED)
        .first()
    )


def claim_pending_batch(
    company,
    watch_slug: str,
    *,
    pick_policy: str | None = None,
    schedule_slug: str = "",
    consumed_by: str = "",
) -> WatchBatch | None:
    """
    Resuelve Watch activo (no archivado) por company+slug.
    Selecciona un lote pending con select_for_update (FIFO/LIFO).
    Marca claimed → consumed. Retorna el batch o None.
    """
    watch = get_watch_by_slug(company, watch_slug)
    if watch is None:
        return None
    if watch.status != Watch.STATUS_ACTIVE:
        return None

    policy = (pick_policy or watch.pending_pick_policy or Watch.PICK_FIFO).lower()
    order = "created_at" if policy == Watch.PICK_FIFO else "-created_at"

    by = (consumed_by or "").strip()
    if not by and schedule_slug:
        by = f"schedule:{schedule_slug}"
    if not by:
        by = "claim"

    with transaction.atomic():
        batch = (
            WatchBatch.objects.select_for_update()
            .filter(watch=watch, status=WatchBatch.STATUS_PENDING)
            .order_by(order)
            .first()
        )
        if batch is None:
            return None
        now = timezone.now()
        batch.status = WatchBatch.STATUS_CLAIMED
        batch.save(update_fields=["status", "updated_at"])
        batch.status = WatchBatch.STATUS_CONSUMED
        batch.consumed_at = now
        batch.consumed_by = by[:128]
        batch.save(update_fields=["status", "consumed_at", "consumed_by", "updated_at"])
        audit_svc.append_event(
            watch,
            WatchAuditEvent.EVENT_BATCH_CLAIM,
            None,
            {
                "triggered_by": "system:file_watch",
                "batch_id": str(batch.id),
                "content_hash": batch.content_hash,
                "consumed_by": batch.consumed_by,
                "pick_policy": policy,
            },
        )
        return batch
