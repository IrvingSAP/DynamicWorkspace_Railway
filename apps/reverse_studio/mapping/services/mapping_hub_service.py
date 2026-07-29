"""Contexto hub de mapeo Reverse Studio (mapping_rules.md)."""

from apps.dms.field_mapping.services import field_mapping_service
from apps.dms.transform_rules.services import transform_rules_service


def get_mapping_hub_summary(project, membership=None) -> dict:
    """Resumen para hub de mapeo y hub de proyecto."""
    editor = field_mapping_service.get_editor_context(project, membership)
    hub = editor["hub"]
    rules = transform_rules_service.get_editor_context(project, membership)
    rules_hub = rules["hub"]
    return {
        "mappings_count": hub.mappings_count,
        "source_fields_count": hub.source_fields_count,
        "target_fields_count": hub.target_fields_count,
        "unmapped_required": hub.unmapped_required,
        "is_complete": hub.is_complete,
        "status_label": hub.status_label,
        "pipelines_with_steps": rules_hub.pipelines_with_steps,
        "total_rule_steps": rules_hub.total_steps,
        "rules_status_label": rules_hub.status_label,
        "version_label": hub.version_label,
        "has_source_fields": bool(editor.get("source_fields")),
        "has_target_fields": bool(editor.get("target_fields")),
        "has_mappings": hub.mappings_count > 0,
    }
