import uuid

from django.db import models

from apps.dms.source_profile.models import DmsMappingVersion


class DmsFieldMappingSet(models.Model):
    """Conjunto de mapeos origen→destino por versión (field_mapping.md)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField(
        DmsMappingVersion,
        on_delete=models.CASCADE,
        related_name="field_mapping_set",
    )
    mappings = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conjunto de mapeos DMS"
        verbose_name_plural = "Conjuntos de mapeos DMS"

    def __str__(self) -> str:
        return f"Mappings — {self.version} ({len(self.mappings or [])})"
