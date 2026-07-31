"""PROFILE_SEED models — auditoría de semillas (apply_draft.md M3)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.projects.models import Project


class ProfileSeedEvent(models.Model):
    """Auditoría de importación de estructura publicada → borrador destino."""

    STATUS_OK = "ok"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_OK, "OK"),
        (STATUS_FAILED, "Fallido"),
    )

    MODE_CLONE_SNAPSHOT = "clone_snapshot"

    SLOT_PROFILE_A = "profile_a"
    SLOT_SCHEMA = "schema"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="profile_seed_events",
    )
    target_slot = models.CharField(max_length=40, default=SLOT_PROFILE_A)
    source_project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_seed_events_as_source",
    )
    source_kind = models.CharField(max_length=40)
    source_slot = models.CharField(max_length=40, default=SLOT_SCHEMA)
    source_version = models.PositiveIntegerField(default=0)
    source_slug = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OK,
    )
    message = models.TextField(blank=True, default="")
    mode = models.CharField(max_length=40, default=MODE_CLONE_SNAPSHOT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_seed_events_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PROFILE SEED event"
        verbose_name_plural = "PROFILE SEED events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["target_project", "-created_at"],
                name="ps_event_target_created_idx",
            ),
        ]

    def __str__(self) -> str:
        src = self.source_slug or (
            self.source_project.slug if self.source_project_id else "?"
        )
        return f"{src} → {self.target_project.slug}:{self.target_slot} · {self.status}"
