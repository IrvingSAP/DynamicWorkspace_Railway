import uuid

from django.conf import settings
from django.db import models

from apps.projects.models import Project


class DmsMappingVersion(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador"),
        (STATUS_PUBLISHED, "Publicada"),
        (STATUS_ARCHIVED, "Archivada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="dms_versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_versions_published",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Versión DMS de mapping"
        verbose_name_plural = "Versiones DMS de mapping"
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version_number"],
                name="dms_mappingversion_project_version_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"]),
        ]

    def __str__(self) -> str:
        return f"v{self.version_number} ({self.status}) — {self.project.slug}"


class DmsSourceProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField(
        DmsMappingVersion,
        on_delete=models.CASCADE,
        related_name="source_profile",
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
        verbose_name = "Perfil de origen DMS"
        verbose_name_plural = "Perfiles de origen DMS"

    def __str__(self) -> str:
        return f"Source — {self.version}"
