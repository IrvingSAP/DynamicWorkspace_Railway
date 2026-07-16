import uuid

from django.db import models

from apps.dms.constants import (
    APPLIES_TO_CHOICES,
    ERROR_PHASE_CHOICES,
    PHASE_2_ONLY_CHOICES,
    PHASE_CHOICES,
    SEVERITY_CHOICES,
)


class CatalogBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "code"]

    def __str__(self) -> str:
        return self.name


class SourceFileType(CatalogBase):
    extensions = models.JSONField(default=list)
    parser_key = models.CharField(max_length=120)
    phase = models.CharField(max_length=16, choices=PHASE_CHOICES, default="mvp")
    config_schema = models.JSONField(blank=True, null=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Tipo de archivo de lectura"
        verbose_name_plural = "Tipos de archivo de lectura"


class TargetFileType(CatalogBase):
    extensions = models.JSONField(default=list)
    serializer_key = models.CharField(max_length=120)
    phase = models.CharField(max_length=16, choices=PHASE_CHOICES, default="mvp")
    config_schema = models.JSONField(blank=True, null=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Tipo de archivo de salida"
        verbose_name_plural = "Tipos de archivo de salida"


class CharsetEncoding(CatalogBase):
    charset_value = models.CharField(max_length=64, blank=True, default="")
    is_auto_detect = models.BooleanField(default=False)

    class Meta(CatalogBase.Meta):
        verbose_name = "Codificación de caracteres"
        verbose_name_plural = "Codificaciones de caracteres"


class LineEnding(CatalogBase):
    sequence = models.CharField(max_length=32, blank=True, default="")
    is_auto_detect = models.BooleanField(default=False)
    allows_custom_value = models.BooleanField(default=False)

    class Meta(CatalogBase.Meta):
        verbose_name = "Final de línea"
        verbose_name_plural = "Finales de línea"


class FieldContentType(CatalogBase):
    default_pattern = models.CharField(max_length=255, blank=True, default="")
    requires_date_format = models.BooleanField(default=False)
    allows_custom_pattern = models.BooleanField(default=False)
    phase = models.CharField(max_length=16, choices=PHASE_2_ONLY_CHOICES, default="mvp")

    class Meta(CatalogBase.Meta):
        verbose_name = "Tipo de contenido de campo origen"
        verbose_name_plural = "Tipos de contenido de campo origen"


class CaptureBoundaryMode(CatalogBase):
    applies_to = models.CharField(max_length=8, choices=APPLIES_TO_CHOICES, default="both")
    param_schema = models.JSONField(blank=True, null=True)
    phase = models.CharField(max_length=16, choices=PHASE_2_ONLY_CHOICES, default="mvp")

    class Meta(CatalogBase.Meta):
        verbose_name = "Modo de inicio/fin de captura"
        verbose_name_plural = "Modos de inicio/fin de captura"


class TargetFieldDataType(CatalogBase):
    default_date_format = models.CharField(max_length=64, blank=True, default="")
    requires_format = models.BooleanField(default=False)
    excel_type = models.CharField(max_length=32, blank=True, default="")
    suggested_content_types = models.JSONField(default=list, blank=True)
    phase = models.CharField(max_length=16, choices=PHASE_2_ONLY_CHOICES, default="mvp")

    class Meta(CatalogBase.Meta):
        verbose_name = "Tipo de dato de campo destino"
        verbose_name_plural = "Tipos de dato de campo destino"


class ExecutionErrorCode(CatalogBase):
    phase = models.CharField(max_length=16, choices=ERROR_PHASE_CHOICES, default="parse")
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="error")

    class Meta(CatalogBase.Meta):
        verbose_name = "Código de error de ejecución"
        verbose_name_plural = "Códigos de error de ejecución"


class FilenamePatternVariable(CatalogBase):
    syntax = models.CharField(max_length=64)
    supports_format = models.BooleanField(default=False)
    example_value = models.CharField(max_length=120, blank=True, default="")
    resolver_key = models.CharField(max_length=120)

    class Meta(CatalogBase.Meta):
        verbose_name = "Variable de patrón de nombre"
        verbose_name_plural = "Variables de patrón de nombre"


class ValueGeneratorType(CatalogBase):
    resolver_key = models.CharField(max_length=120)
    param_schema = models.JSONField(blank=True, null=True)
    phase = models.CharField(max_length=16, choices=PHASE_2_ONLY_CHOICES, default="mvp")

    class Meta(CatalogBase.Meta):
        verbose_name = "Tipo de generador de valor"
        verbose_name_plural = "Tipos de generador de valor"


class PermissionPackage(CatalogBase):
    maps_to_role = models.CharField(
        max_length=2,
        help_text="Rol ProjectMembership: PA | ED | CO | GE",
    )
    permissions = models.JSONField(default=list, blank=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Paquete de permisos"
        verbose_name_plural = "Paquetes de permisos"


class TransformOperation(CatalogBase):
    resolver_key = models.CharField(max_length=120)
    param_schema = models.JSONField(blank=True, null=True)
    phase = models.CharField(max_length=16, choices=PHASE_2_ONLY_CHOICES, default="mvp")

    class Meta(CatalogBase.Meta):
        verbose_name = "Operación de transformación"
        verbose_name_plural = "Operaciones de transformación"


class TransformPipelineTemplate(CatalogBase):
    pipeline = models.JSONField(default=list, blank=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Plantilla de pipeline"
        verbose_name_plural = "Plantillas de pipeline"


from apps.dms.mapping.models import DmsProjectConfig  # noqa: E402, F401
from apps.dms.source_profile.models import DmsMappingVersion, DmsSourceProfile  # noqa: E402, F401
from apps.dms.target_profile.models import DmsTargetProfile  # noqa: E402, F401
from apps.dms.field_mapping.models import DmsFieldMappingSet  # noqa: E402, F401
from apps.dms.file_intake.models import DmsExecutionJob, DmsSampleFile  # noqa: E402, F401
