from dataclasses import dataclass, field

from apps.dms import models


@dataclass(frozen=True)
class CatalogColumn:
    key: str
    label: str
    mono: bool = False


@dataclass(frozen=True)
class CatalogField:
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    readonly_on_edit: bool = False
    help_text: str = ""
    choices: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogDef:
    slug: str
    title: str
    entity: str
    usage: str
    model: type
    columns: list[CatalogColumn]
    form_fields: list[CatalogField]
    group: str = ""


CATALOGS: dict[str, CatalogDef] = {
    "source-file-types": CatalogDef(
        slug="source-file-types",
        title="Tipos archivo lectura",
        entity="SourceFileType",
        usage="Origen — Paso 1",
        model=models.SourceFileType,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("extensions", "Extensiones", mono=True),
            CatalogColumn("parser_key", "Parser", mono=True),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField(
                "extensions",
                "Extensiones (JSON)",
                field_type="json",
                required=True,
                help_text='Ej: [".txt", ".csv"]',
            ),
            CatalogField("parser_key", "Parser key", required=True),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2"), ("phase_3", "Fase 3")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
            CatalogField("config_schema", "Config schema (JSON)", field_type="json"),
        ],
    ),
    "target-file-types": CatalogDef(
        slug="target-file-types",
        title="Tipos archivo salida",
        entity="TargetFileType",
        usage="Destino — Paso 1",
        model=models.TargetFileType,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("extensions", "Extensiones", mono=True),
            CatalogColumn("serializer_key", "Serializer", mono=True),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField(
                "extensions",
                "Extensiones (JSON)",
                field_type="json",
                required=True,
            ),
            CatalogField("serializer_key", "Serializer key", required=True),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2"), ("phase_3", "Fase 3")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
            CatalogField("config_schema", "Config schema (JSON)", field_type="json"),
        ],
    ),
    "charset-encodings": CatalogDef(
        slug="charset-encodings",
        title="Codificaciones",
        entity="CharsetEncoding",
        usage="Origen y destino — encoding",
        model=models.CharsetEncoding,
        group="text-read-format",
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("charset_value", "Valor codec", mono=True),
            CatalogColumn("is_auto_detect", "Auto-detect"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("charset_value", "Valor codec"),
            CatalogField("is_auto_detect", "Detección automática", field_type="checkbox"),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "line-endings": CatalogDef(
        slug="line-endings",
        title="Finales de línea",
        entity="LineEnding",
        usage="Origen y destino — line ending",
        model=models.LineEnding,
        group="text-read-format",
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("sequence", "Secuencia", mono=True),
            CatalogColumn("is_auto_detect", "Auto-detect"),
            CatalogColumn("allows_custom_value", "Permite custom"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("sequence", "Secuencia"),
            CatalogField("is_auto_detect", "Detección automática", field_type="checkbox"),
            CatalogField(
                "allows_custom_value",
                "Permite valor personalizado",
                field_type="checkbox",
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "field-content-types": CatalogDef(
        slug="field-content-types",
        title="Tipos contenido campo origen",
        entity="FieldContentType",
        usage="Origen — Paso 4",
        model=models.FieldContentType,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("default_pattern", "Patrón default", mono=True),
            CatalogColumn("requires_date_format", "Req. date format"),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("default_pattern", "Patrón por defecto"),
            CatalogField(
                "requires_date_format",
                "Requiere formato de fecha",
                field_type="checkbox",
            ),
            CatalogField(
                "allows_custom_pattern",
                "Permite patrón propio",
                field_type="checkbox",
            ),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "capture-boundary-modes": CatalogDef(
        slug="capture-boundary-modes",
        title="Modos inicio/fin captura",
        entity="CaptureBoundaryMode",
        usage="Origen — Pasos 2–3",
        model=models.CaptureBoundaryMode,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("applies_to", "Aplica a"),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField(
                "applies_to",
                "Aplica a",
                field_type="select",
                required=True,
                choices=[("start", "Inicio"), ("end", "Fin"), ("both", "Ambos")],
            ),
            CatalogField("param_schema", "Param schema (JSON)", field_type="json"),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "target-field-data-types": CatalogDef(
        slug="target-field-data-types",
        title="Tipos dato campo destino",
        entity="TargetFieldDataType",
        usage="Destino — Paso 4",
        model=models.TargetFieldDataType,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("requires_format", "Req. formato"),
            CatalogColumn("excel_type", "Excel type", mono=True),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("default_date_format", "Formato fecha por defecto"),
            CatalogField("requires_format", "Requiere formato", field_type="checkbox"),
            CatalogField("excel_type", "Tipo Excel"),
            CatalogField(
                "suggested_content_types",
                "Content types sugeridos (JSON)",
                field_type="json",
            ),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "execution-error-codes": CatalogDef(
        slug="execution-error-codes",
        title="Códigos de error",
        entity="ExecutionErrorCode",
        usage="Informes de ejecución",
        model=models.ExecutionErrorCode,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("phase", "Etapa"),
            CatalogColumn("severity", "Severidad"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField(
                "phase",
                "Etapa",
                field_type="select",
                required=True,
                choices=[
                    ("parse", "Parseo"),
                    ("map", "Mapeo"),
                    ("transform", "Transformación"),
                    ("write", "Escritura"),
                    ("job", "Job"),
                ],
            ),
            CatalogField(
                "severity",
                "Severidad",
                field_type="select",
                required=True,
                choices=[("error", "Error"), ("warning", "Advertencia")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "filename-pattern-variables": CatalogDef(
        slug="filename-pattern-variables",
        title="Variables patrón nombre",
        entity="FilenamePatternVariable",
        usage="Destino — nombre de salida",
        model=models.FilenamePatternVariable,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("syntax", "Sintaxis", mono=True),
            CatalogColumn("supports_format", "Soporta formato"),
            CatalogColumn("resolver_key", "Resolver", mono=True),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("syntax", "Sintaxis", required=True),
            CatalogField("supports_format", "Soporta formato strftime", field_type="checkbox"),
            CatalogField("example_value", "Valor ejemplo"),
            CatalogField("resolver_key", "Resolver key", required=True),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "value-generator-types": CatalogDef(
        slug="value-generator-types",
        title="Tipos generador de valor",
        entity="ValueGeneratorType",
        usage="Field mapping — generated",
        model=models.ValueGeneratorType,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("resolver_key", "Resolver", mono=True),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("resolver_key", "Resolver key", required=True),
            CatalogField("param_schema", "Param schema (JSON)", field_type="json"),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "permission-packages": CatalogDef(
        slug="permission-packages",
        title="Paquetes de permisos",
        entity="PermissionPackage",
        usage="Proyecto — miembros",
        model=models.PermissionPackage,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("maps_to_role", "Rol", mono=True),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField(
                "maps_to_role",
                "Rol membership",
                field_type="select",
                required=True,
                choices=[
                    ("PA", "PA — Admin"),
                    ("ED", "ED — Editor"),
                    ("CO", "CO — Consulta"),
                    ("GE", "GE — Generar"),
                ],
            ),
            CatalogField("permissions", "Permisos (JSON)", field_type="json"),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "transform-operations": CatalogDef(
        slug="transform-operations",
        title="Operaciones de transformación",
        entity="TransformOperation",
        usage="Transform rules / field mapping",
        model=models.TransformOperation,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("resolver_key", "Resolver", mono=True),
            CatalogColumn("phase", "Fase"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("resolver_key", "Resolver key", required=True),
            CatalogField("param_schema", "Param schema (JSON)", field_type="json"),
            CatalogField(
                "phase",
                "Fase",
                field_type="select",
                required=True,
                choices=[("mvp", "MVP"), ("phase_2", "Fase 2")],
            ),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
    "transform-pipeline-templates": CatalogDef(
        slug="transform-pipeline-templates",
        title="Plantillas de pipeline",
        entity="TransformPipelineTemplate",
        usage="Transform rules — aplicar plantilla",
        model=models.TransformPipelineTemplate,
        columns=[
            CatalogColumn("code", "Código", mono=True),
            CatalogColumn("name", "Nombre"),
            CatalogColumn("sort_order", "Orden", mono=True),
            CatalogColumn("is_active", "Activo"),
        ],
        form_fields=[
            CatalogField("code", "Código", required=True, readonly_on_edit=True),
            CatalogField("name", "Nombre", required=True),
            CatalogField("description", "Descripción", field_type="textarea"),
            CatalogField("pipeline", "Pipeline (JSON)", field_type="json", required=True),
            CatalogField("sort_order", "Orden", field_type="integer", required=True),
            CatalogField("is_active", "Activo", field_type="checkbox"),
        ],
    ),
}


def get_catalog(slug: str) -> CatalogDef:
    if slug not in CATALOGS:
        raise KeyError(slug)
    return CATALOGS[slug]


def hub_entries() -> list[dict]:
    rows = []
    for catalog in CATALOGS.values():
        rows.append(
            {
                "slug": catalog.slug,
                "title": catalog.title,
                "entity": catalog.entity,
                "usage": catalog.usage,
                "count": catalog.model.objects.count(),
                "group": catalog.group,
            }
        )
    return rows
