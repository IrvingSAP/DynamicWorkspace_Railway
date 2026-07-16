"""Contexto UI del asistente Transform Rules (transform_rules.md)."""

from dataclasses import dataclass

from apps.dms.field_mapping.services import field_mapping_persistence_service
from apps.dms.field_mapping.services.field_mapping_service import get_sample_preview_row
from apps.dms.transform_rules.services import transform_rules_persistence_service
from apps.dms.transform_rules.services.transform_catalog_service import (
    list_transform_op_options,
)


@dataclass
class RulesHubContext:
    project_name: str
    project_slug: str
    membership_role: str
    version_label: str
    version_number: int
    mappings_count: int
    pipelines_with_steps: int
    total_steps: int
    is_complete: bool
    status_label: str


def get_editor_context(project, membership) -> dict:
    version = field_mapping_persistence_service.get_or_create_draft_with_mappings(project)
    data = field_mapping_persistence_service.get_mappings_dict(project)
    mappings = [m for m in (data.get("mappings") or []) if m.get("is_active", True)]

    rows = []
    total_steps = 0
    with_steps = 0
    for mapping in mappings:
        pipeline = mapping.get("transform_pipeline") or []
        total_steps += len(pipeline)
        if pipeline:
            with_steps += 1
        rows.append(
            {
                "target_field": mapping.get("target_field") or "",
                "mapping_kind": mapping.get("mapping_kind") or "",
                "source_summary": _source_summary(mapping),
                "transform_pipeline": pipeline,
                "ops_label": " → ".join(step.get("op") or "" for step in pipeline) or "(sin reglas)",
            }
        )

    errors, _warnings = transform_rules_persistence_service.validate_mappings_pipelines(
        mappings, strict=True
    )
    is_complete = bool(mappings) and not errors
    role = membership.role if membership else "—"
    sample_row = get_sample_preview_row(project)

    return {
        "version": version,
        "rule_rows": rows,
        "transform_ops": list_transform_op_options(active_only=True),
        "pipeline_templates": transform_rules_persistence_service.list_pipeline_templates(
            active_only=True
        ),
        "sample_preview_row": sample_row,
        "has_sample_preview": sample_row is not None,
        "mappings": mappings,
        "is_complete": is_complete,
        "hub": RulesHubContext(
            project_name=project.name,
            project_slug=project.slug,
            membership_role=role,
            version_label=f"Borrador v{version.version_number}",
            version_number=version.version_number,
            mappings_count=len(mappings),
            pipelines_with_steps=with_steps,
            total_steps=total_steps,
            is_complete=is_complete,
            status_label="Listo" if is_complete else ("Sin mapeos" if not mappings else "En edición"),
        ),
    }


def _source_summary(mapping: dict) -> str:
    kind = mapping.get("mapping_kind") or ""
    if kind == "constant":
        return f'constante "{mapping.get("value") or ""}"'
    if kind == "generated":
        gen = mapping.get("generator") or {}
        return f"generado:{gen.get('type') or '?'}"
    if kind == "concat":
        return "concat"
    fields = mapping.get("source_fields") or []
    return ", ".join(fields) if fields else "—"
