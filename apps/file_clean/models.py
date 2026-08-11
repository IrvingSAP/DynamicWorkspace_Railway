import uuid

from django.conf import settings
from django.db import models

from apps.dms.source_profile.models import DmsMappingVersion
from apps.projects.models import Project


class CleanJob(models.Model):
    """Una ejecución de limpieza File Clean (clean_run.md Módulo 5)."""

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="file_clean_jobs",
    )
    published_version = models.ForeignKey(
        DmsMappingVersion,
        on_delete=models.PROTECT,
        related_name="file_clean_jobs",
    )
    published_version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_RUNNING
    )
    dry_run = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=128, blank=True, default="", db_index=True)

    input_original_filename = models.CharField(max_length=255, blank=True, default="")
    input_stored_path = models.CharField(max_length=512, blank=True, default="")
    input_size_bytes = models.BigIntegerField(default=0)
    input_content_hash = models.CharField(max_length=64, blank=True, default="")
    input_mime_type = models.CharField(max_length=128, blank=True, default="")

    output_filename = models.CharField(max_length=255, blank=True, default="")
    output_stored_path = models.CharField(max_length=512, blank=True, default="")
    output_size_bytes = models.BigIntegerField(default=0)
    output_content_hash = models.CharField(max_length=64, blank=True, default="")

    change_log_path = models.CharField(max_length=512, blank=True, default="")
    metrics = models.JSONField(default=dict, blank=True)
    preview = models.JSONField(default=dict, blank=True)
    rules_snapshot = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="file_clean_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "FILE CLEAN — Job"
        verbose_name_plural = "FILE CLEAN — Jobs"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="file_clean_job_idempotency_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"CleanJob {self.id} — {self.project.slug}"
