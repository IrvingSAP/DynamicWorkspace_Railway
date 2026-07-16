"""Contexto UI del asistente Field Mapping (field_mapping.md)."""

from dataclasses import dataclass

from apps.dms.field_mapping.services import field_mapping_persistence_service
from apps.dms.file_intake.models import DmsSampleFile
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.services import target_persistence_service

MAPPING_KIND_OPTIONS = [
    {"code": "direct", "name": "Directo (1:1)", "phase": "mvp"},
    {"code": "constant", "name": "Constante", "phase": "mvp"},
    {"code": "concat", "name": "Concatenar", "phase": "mvp"},
    {"code": "generated", "name": "Generado", "phase": "mvp"},
    {"code": "split", "name": "Dividir (1:N)", "phase": "mvp"},
    {"code": "expression", "name": "Expresión", "phase": "mvp"},
]

GENERATOR_OPTIONS = [
    {"code": "sequence_numeric", "name": "Secuencia numérica"},
    {"code": "sequence_padded", "name": "Secuencia con padding"},
    {"code": "sequence_alphanumeric", "name": "Secuencia alfanumérica"},
    {"code": "sequence_template", "name": "Plantilla con secuencia"},
    {"code": "unique_uuid", "name": "UUID por fila"},
    {"code": "unique_job_counter", "name": "Correlativo por job"},
    {"code": "job_timestamp", "name": "Fecha/hora de ejecución"},
    {"code": "row_number", "name": "Número de fila"},
]

TRANSFORM_OPTIONS = [
    {"code": "trim", "name": "Trim"},
    {"code": "upper", "name": "Mayúsculas"},
    {"code": "lower", "name": "Minúsculas"},
    {"code": "date_format", "name": "Formato fecha"},
    {"code": "pad_left", "name": "Pad izquierda"},
    {"code": "pad_right", "name": "Pad derecha"},
    {"code": "default_if_empty", "name": "Default si vacío"},
]


def _transform_ops_for_mapping_ui() -> list[dict]:
    try:
        from apps.dms.transform_rules.services.transform_catalog_service import (
            list_transform_op_options,
        )

        rows = list_transform_op_options(active_only=True)
        if rows:
            return [{"code": row["code"], "name": row["name"]} for row in rows]
    except Exception:
        pass
    return list(TRANSFORM_OPTIONS)


@dataclass
class MappingHubContext:
    project_name: str
    project_slug: str
    membership_role: str
    version_label: str
    version_number: int
    mappings_count: int
    source_fields_count: int
    target_fields_count: int
    unmapped_required: int
    is_complete: bool
    status_label: str


def _generator_types_from_catalog() -> list[dict]:
    try:
        from apps.dms.models import ValueGeneratorType

        rows = list(
            ValueGeneratorType.objects.filter(is_active=True).order_by("sort_order", "code")
        )
        if rows:
            return [{"code": row.code, "name": row.name} for row in rows]
    except Exception:
        pass
    return list(GENERATOR_OPTIONS)


def get_sample_preview_row(project) -> dict | None:
    """Primera fila parseada del último archivo muestra del proyecto."""
    sample = (
        DmsSampleFile.objects.filter(project=project).order_by("-created_at").first()
    )
    if sample is None or not sample.stored_path:
        return None
    try:
        from apps.dms.file_intake.services.storage_service import absolute_from_stored
        from apps.dms.transform_execution.services.source_parser_service import (
            parse_source_file,
        )

        source = source_persistence_service.get_source_dict(project)
        if not (source.get("fields") or []):
            return None
        path = absolute_from_stored(sample.stored_path)
        if not path.is_file():
            return None
        result = parse_source_file(path, source, limit=1)
        if not result.rows:
            return None
        return dict(result.rows[0].data or {})
    except Exception:
        return None


def _sample_preview_row(project) -> dict | None:
    return get_sample_preview_row(project)


def get_editor_context(project, membership) -> dict:
    version = field_mapping_persistence_service.get_or_create_draft_with_mappings(project)
    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)
    mappings_data = field_mapping_persistence_service.get_mappings_dict(project)
    mappings = mappings_data.get("mappings") or []

    source_fields = source.get("fields") or []
    target_fields = target.get("fields") or []
    mapped_targets = {
        (item.get("target_field") or "").strip().lower()
        for item in mappings
        if item.get("is_active", True)
    }
    unmapped_required = [
        field
        for field in target_fields
        if bool(field.get("required"))
        and (field.get("name") or "").strip().lower() not in mapped_targets
        and field.get("default_value") in (None, "")
    ]
    errors, _warnings = field_mapping_persistence_service.validate_mappings_dict(
        mappings_data,
        source_fields=source_fields,
        target_fields=target_fields,
        strict=True,
    )
    is_complete = not errors and bool(target_fields)

    role = membership.role if membership else "—"
    return {
        "version": version,
        "source_fields": source_fields,
        "target_fields": target_fields,
        "mappings": mappings,
        "mapping_kinds": MAPPING_KIND_OPTIONS,
        "generator_types": _generator_types_from_catalog(),
        "transform_ops": _transform_ops_for_mapping_ui(),
        "suggestions": field_mapping_persistence_service.suggest_direct_mappings(
            source_fields, target_fields
        ),
        "unmapped_required_count": len(unmapped_required),
        "is_complete": is_complete,
        "source_file_type": source.get("file_type_code") or "—",
        "target_file_type": target.get("file_type_code") or "—",
        "sample_preview_row": _sample_preview_row(project),
        "hub": MappingHubContext(
            project_name=project.name,
            project_slug=project.slug,
            membership_role=role,
            version_label=f"Borrador v{version.version_number}",
            version_number=version.version_number,
            mappings_count=len(mappings),
            source_fields_count=len(source_fields),
            target_fields_count=len(target_fields),
            unmapped_required=len(unmapped_required),
            is_complete=is_complete,
            status_label="Completo" if is_complete else "En edición",
        ),
    }
