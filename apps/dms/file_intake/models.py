import uuid

from django.conf import settings
from django.db import models

from apps.dms.source_profile.models import DmsMappingVersion
from apps.projects.models import Project


class DmsSampleFile(models.Model):
    """Archivo muestra del wizard de definición (file_intake.md)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="dms_sample_files",
    )
    version = models.ForeignKey(
        DmsMappingVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sample_files",
    )
    original_filename = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=500)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    mime_type = models.CharField(max_length=120, blank=True, default="")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_sample_uploads",
    )
    suggestions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Archivo muestra DMS"
        verbose_name_plural = "Archivos muestra DMS"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.project.slug})"


class DmsExecutionJob(models.Model):
    """Job de ejecución Fase C — upload input vive aquí (file_intake + transform_execution)."""

    JOB_PREVIEW = "preview"
    JOB_FULL = "full"
    JOB_TYPE_CHOICES = (
        (JOB_PREVIEW, "Preview"),
        (JOB_FULL, "Completo"),
    )

    STATUS_UPLOADED = "uploaded"
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Subido"),
        (STATUS_QUEUED, "En cola"),
        (STATUS_RUNNING, "En ejecución"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_PARTIAL, "Parcial"),
        (STATUS_FAILED, "Fallido"),
        (STATUS_CANCELLED, "Cancelado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="dms_execution_jobs",
    )
    version = models.ForeignKey(
        DmsMappingVersion,
        on_delete=models.PROTECT,
        related_name="execution_jobs",
    )
    job_type = models.CharField(max_length=16, choices=JOB_TYPE_CHOICES, default=JOB_FULL)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_UPLOADED
    )
    input_original_filename = models.CharField(max_length=255, blank=True, default="")
    input_stored_path = models.CharField(max_length=500, blank=True, default="")
    input_size_bytes = models.PositiveBigIntegerField(default=0)
    input_content_hash = models.CharField(max_length=64, blank=True, default="")
    input_mime_type = models.CharField(max_length=120, blank=True, default="")
    input_suggestions = models.JSONField(default=dict, blank=True)
    output_filename = models.CharField(max_length=255, blank=True, default="")
    output_stored_path = models.CharField(max_length=500, blank=True, default="")
    output_size_bytes = models.PositiveBigIntegerField(default=0)
    report_path = models.CharField(max_length=500, blank=True, default="")
    rows_read = models.PositiveIntegerField(default=0)
    rows_ok = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_execution_jobs",
    )
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Job de ejecución DMS"
        verbose_name_plural = "Jobs de ejecución DMS"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Job {self.id} — {self.project.slug} ({self.status})"
