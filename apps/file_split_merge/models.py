import uuid

from django.conf import settings
from django.db import models

from apps.dms.source_profile.models import DmsMappingVersion
from apps.projects.models import Project


class SplitMergeJob(models.Model):
    """Una ejecución Split o Merge (sm_run.md Módulo 5)."""

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "En cola"),
        (STATUS_RUNNING, "En curso"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_FAILED, "Fallido"),
    ]

    OPERATION_SPLIT = "split"
    OPERATION_MERGE = "merge"
    OPERATION_CHOICES = [
        (OPERATION_SPLIT, "Split"),
        (OPERATION_MERGE, "Merge"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="file_split_merge_jobs",
    )
    published_version = models.ForeignKey(
        DmsMappingVersion,
        on_delete=models.PROTECT,
        related_name="file_split_merge_jobs",
    )
    published_version_number = models.PositiveIntegerField()
    operation = models.CharField(max_length=16, choices=OPERATION_CHOICES)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_RUNNING
    )
    dry_run = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=128, blank=True, default="", db_index=True)

    # [{filename, stored_path, size_bytes, content_hash, mime}]
    inputs = models.JSONField(default=list, blank=True)
    # [{kind, filename, stored_path, size_bytes, content_hash, part_key?}]
    outputs = models.JSONField(default=list, blank=True)
    manifest_path = models.CharField(max_length=512, blank=True, default="")

    metrics = models.JSONField(default=dict, blank=True)
    preview = models.JSONField(default=dict, blank=True)
    rules_snapshot = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="file_split_merge_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "FILE SPLIT/MERGE — Job"
        verbose_name_plural = "FILE SPLIT/MERGE — Jobs"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="file_sm_job_idempotency_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"SplitMergeJob {self.id} — {self.project.slug}"
