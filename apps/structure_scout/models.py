import uuid

from django.conf import settings
from django.db import models

from apps.dms.file_intake.models import DmsSampleFile
from apps.projects.models import Project


class ScoutDetectionState(models.Model):
    """Patrón de archivo confirmado/ajustado para un proyecto STRUCTURE SCOUT (M3)."""

    STATUS_IDLE = "idle"
    STATUS_DRAFT_READY = "draft_ready"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_IDLE, "Sin confirmar"),
        (STATUS_DRAFT_READY, "Listo"),
        (STATUS_NEEDS_REVIEW, "Requiere revisión"),
        (STATUS_FAILED, "Fallido"),
    )

    CONFIDENCE_HIGH = "high"
    CONFIDENCE_MEDIUM = "medium"
    CONFIDENCE_LOW = "low"
    CONFIDENCE_CHOICES = (
        (CONFIDENCE_HIGH, "Alta"),
        (CONFIDENCE_MEDIUM, "Media"),
        (CONFIDENCE_LOW, "Baja"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="scout_detection",
    )
    sample = models.ForeignKey(
        DmsSampleFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_detections",
    )
    file_type_code = models.CharField(max_length=40, blank=True, default="")
    encoding_code = models.CharField(max_length=40, blank=True, default="utf-8")
    line_ending_code = models.CharField(max_length=10, blank=True, default="lf")
    delimiter = models.CharField(max_length=8, blank=True, default="")
    has_header = models.BooleanField(default=True)
    header_row = models.PositiveSmallIntegerField(null=True, blank=True, default=1)
    confidence = models.CharField(
        max_length=16,
        choices=CONFIDENCE_CHOICES,
        blank=True,
        default="",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IDLE,
    )
    notes = models.TextField(blank=True, default="")
    suggestions_snapshot = models.JSONField(default=dict, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_detections_confirmed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Detección STRUCTURE SCOUT"
        verbose_name_plural = "Detecciones STRUCTURE SCOUT"

    def __str__(self) -> str:
        return f"{self.project.slug} · {self.status}"


class ScoutFieldsState(models.Model):
    """Campos propuestos/confirmados para un proyecto STRUCTURE SCOUT (M4)."""

    STATUS_IDLE = "idle"
    STATUS_DRAFT_READY = "draft_ready"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_IDLE, "Sin confirmar"),
        (STATUS_DRAFT_READY, "Listo"),
        (STATUS_NEEDS_REVIEW, "Requiere revisión"),
        (STATUS_FAILED, "Fallido"),
    )

    CONFIDENCE_HIGH = "high"
    CONFIDENCE_MEDIUM = "medium"
    CONFIDENCE_LOW = "low"
    CONFIDENCE_CHOICES = (
        (CONFIDENCE_HIGH, "Alta"),
        (CONFIDENCE_MEDIUM, "Media"),
        (CONFIDENCE_LOW, "Baja"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="scout_fields",
    )
    sample = models.ForeignKey(
        DmsSampleFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_fields_states",
    )
    detection = models.ForeignKey(
        ScoutDetectionState,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fields_states",
    )
    fields = models.JSONField(default=list, blank=True)
    confidence = models.CharField(
        max_length=16,
        choices=CONFIDENCE_CHOICES,
        blank=True,
        default="",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IDLE,
    )
    notes = models.TextField(blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_fields_confirmed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Campos STRUCTURE SCOUT"
        verbose_name_plural = "Campos STRUCTURE SCOUT"

    def __str__(self) -> str:
        return f"{self.project.slug} · fields · {self.status}"


class StructureDraft(models.Model):
    """Snapshot versionado de estructura STRUCTURE SCOUT (M5)."""

    STATUS_DRAFT_READY = "draft_ready"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_CHOICES = (
        (STATUS_DRAFT_READY, "Listo"),
        (STATUS_NEEDS_REVIEW, "Requiere revisión"),
    )

    CONFIDENCE_HIGH = "high"
    CONFIDENCE_MEDIUM = "medium"
    CONFIDENCE_LOW = "low"
    CONFIDENCE_CHOICES = (
        (CONFIDENCE_HIGH, "Alta"),
        (CONFIDENCE_MEDIUM, "Media"),
        (CONFIDENCE_LOW, "Baja"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="structure_drafts",
    )
    version = models.PositiveIntegerField()
    is_current = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT_READY,
    )
    confidence = models.CharField(
        max_length=16,
        choices=CONFIDENCE_CHOICES,
        blank=True,
        default="",
    )
    payload = models.JSONField(default=dict, blank=True)
    sample = models.ForeignKey(
        DmsSampleFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structure_drafts",
    )
    sample_filename = models.CharField(max_length=255, blank=True, default="")
    sample_hash_short = models.CharField(max_length=16, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structure_drafts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Borrador STRUCTURE SCOUT"
        verbose_name_plural = "Borradores STRUCTURE SCOUT"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version"],
                name="structure_scout_draft_project_version_uniq",
            ),
        ]

    def __str__(self) -> str:
        current = " · current" if self.is_current else ""
        return f"{self.project.slug} · v{self.version}{current}"


class ScoutApply(models.Model):
    """Auditoría de aplicación de StructureDraft a un destino (M6)."""

    STATUS_OK = "ok"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_OK, "OK"),
        (STATUS_FAILED, "Fallido"),
    )

    KIND_FILE_GATE = "file_gate"
    KIND_REVERSE = "reverse"
    KIND_CHOICES = (
        (KIND_FILE_GATE, "FILE GATE"),
        (KIND_REVERSE, "Reverse Studio"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="scout_applies",
    )
    draft = models.ForeignKey(
        StructureDraft,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applies",
    )
    draft_version = models.PositiveIntegerField(default=0)
    target_project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_applies_received",
    )
    target_kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OK,
    )
    message = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_applies_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apply STRUCTURE SCOUT"
        verbose_name_plural = "Applies STRUCTURE SCOUT"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        target = self.target_project.slug if self.target_project else "?"
        return f"{self.project.slug} → {target} · {self.status}"
