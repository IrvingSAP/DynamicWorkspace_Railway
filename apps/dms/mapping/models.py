import uuid

from django.conf import settings
from django.db import models

from apps.projects.models import Project


class DmsProjectConfig(models.Model):
    VISIBILITY_COMPANY = "company"
    VISIBILITY_MEMBERS_ONLY = "members_only"
    VISIBILITY_CHOICES = [
        (VISIBILITY_COMPANY, "Público (compañía)"),
        (VISIBILITY_MEMBERS_ONLY, "Privado"),
    ]

    # FILE GATE bridge (Módulo 6) — pre-check antes de transformar.
    ACCEPT_PASSED = "passed"
    ACCEPT_PASSED_WITH_WARNINGS = "passed_with_warnings"
    FILE_GATE_ACCEPT_CHOICES = [
        (ACCEPT_PASSED, "Solo passed"),
        (ACCEPT_PASSED_WITH_WARNINGS, "passed o passed_with_warnings"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="dms_config",
    )
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_MEMBERS_ONLY,
    )
    current_version = models.ForeignKey(
        "DmsMappingVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    file_gate_enabled = models.BooleanField(default=False)
    file_gate_project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_bridge_configs",
        help_text="Proyecto FILE GATE vinculado (misma compañía).",
    )
    file_gate_accept = models.CharField(
        max_length=32,
        choices=FILE_GATE_ACCEPT_CHOICES,
        default=ACCEPT_PASSED_WITH_WARNINGS,
    )
    file_gate_max_age_days = models.PositiveSmallIntegerField(default=7)
    file_gate_linked_at = models.DateTimeField(null=True, blank=True)
    file_gate_linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_file_gate_links",
    )
    # FILE MATCH bridge (Módulo 8) — qué lado(s) exigir ante el mismo GATE.
    file_gate_require_a = models.BooleanField(default=False)
    file_gate_require_b = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración DMS de proyecto"
        verbose_name_plural = "Configuraciones DMS de proyecto"

    def __str__(self) -> str:
        return f"DMS config — {self.project.slug}"

    @property
    def is_company_visible(self) -> bool:
        return self.visibility == self.VISIBILITY_COMPANY
