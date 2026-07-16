import uuid

from django.db import models

from apps.projects.models import Project


class DmsProjectConfig(models.Model):
    VISIBILITY_COMPANY = "company"
    VISIBILITY_MEMBERS_ONLY = "members_only"
    VISIBILITY_CHOICES = [
        (VISIBILITY_COMPANY, "Público (compañía)"),
        (VISIBILITY_MEMBERS_ONLY, "Privado"),
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
