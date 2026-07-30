import uuid

from django.conf import settings
from django.db import models

from apps.dms.source_profile.models import DmsMappingVersion
from apps.projects.models import Project


class FileMatchSourceB(models.Model):
    """SourceProfile del lado B (contraparte) para proyectos FILE MATCH.

    El lado A sigue en ``DmsSourceProfile`` (OneToOne de la versión).
    Este modelo cumple B12 / A12: slot B distinto.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField(
        DmsMappingVersion,
        on_delete=models.CASCADE,
        related_name="match_source_b",
    )
    file_type_code = models.CharField(max_length=32, blank=True, default="")
    capture_start = models.JSONField(default=dict, blank=True)
    capture_end = models.JSONField(default=dict, blank=True)
    content_rules = models.JSONField(default=dict, blank=True)
    processing_report = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FILE MATCH — Perfil B"
        verbose_name_plural = "FILE MATCH — Perfiles B"

    def __str__(self) -> str:
        return f"Match B — {self.version}"


def default_match_rules() -> dict:
    return {
        "cardinality": "1:1",
        "key": [],
        "compare": [],
        "normalize": {
            "trim": True,
            "case_fold_keys": True,
        },
        "on_duplicate_key": "bucket",
        "verdict": {
            "fail_on_only_a": True,
            "fail_on_only_b": True,
            "fail_on_mismatch": True,
            "fail_on_duplicate_key": False,
        },
    }


class FileMatchRules(models.Model):
    """Reglas de cruce (clave + compare + normalize) para FILE MATCH."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField(
        DmsMappingVersion,
        on_delete=models.CASCADE,
        related_name="match_rules",
    )
    rules = models.JSONField(default=default_match_rules, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FILE MATCH — Reglas de cruce"
        verbose_name_plural = "FILE MATCH — Reglas de cruce"

    def __str__(self) -> str:
        return f"MatchRules — {self.version}"


class FileMatchJob(models.Model):
    """Una conciliación A+B (match_run.md Módulo 5)."""

    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_PARTIAL = "partial"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "En curso"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_FAILED, "Fallido"),
        (STATUS_PARTIAL, "Parcial"),
    ]

    VERDICT_PASSED = "passed"
    VERDICT_FAILED = "failed"
    VERDICT_PARTIAL = "partial"
    VERDICT_CHOICES = [
        (VERDICT_PASSED, "Cuadra"),
        (VERDICT_FAILED, "No cuadra"),
        (VERDICT_PARTIAL, "Parcial"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="file_match_jobs",
    )
    published_version = models.ForeignKey(
        DmsMappingVersion,
        on_delete=models.PROTECT,
        related_name="file_match_jobs",
    )
    published_version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_RUNNING
    )
    verdict = models.CharField(max_length=16, choices=VERDICT_CHOICES, blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    file_a_name = models.CharField(max_length=255, blank=True, default="")
    file_a_path = models.CharField(max_length=512, blank=True, default="")
    file_a_size_bytes = models.BigIntegerField(default=0)
    file_a_hash = models.CharField(max_length=64, blank=True, default="")

    file_b_name = models.CharField(max_length=255, blank=True, default="")
    file_b_path = models.CharField(max_length=512, blank=True, default="")
    file_b_size_bytes = models.BigIntegerField(default=0)
    file_b_hash = models.CharField(max_length=64, blank=True, default="")

    rules_snapshot = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    detail_preview = models.JSONField(default=list, blank=True)
    report_path = models.CharField(max_length=512, blank=True, default="")

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="file_match_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "FILE MATCH — Job"
        verbose_name_plural = "FILE MATCH — Jobs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MatchJob {self.id} — {self.project.slug}"
