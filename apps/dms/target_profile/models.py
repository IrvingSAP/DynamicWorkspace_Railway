import uuid

from django.db import models

from apps.dms.source_profile.models import DmsMappingVersion


class DmsTargetProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField(
        DmsMappingVersion,
        on_delete=models.CASCADE,
        related_name="target_profile",
    )
    file_type_code = models.CharField(max_length=32, blank=True, default="")
    layout = models.JSONField(default=dict, blank=True)
    serialization = models.JSONField(default=dict, blank=True)
    write_validation = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de destino DMS"
        verbose_name_plural = "Perfiles de destino DMS"

    def __str__(self) -> str:
        return f"Target — {self.version}"
