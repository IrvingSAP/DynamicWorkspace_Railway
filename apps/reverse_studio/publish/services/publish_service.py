"""Publicar definición Reverse Studio (publish.md Módulo 4)."""

from dataclasses import dataclass, field

from apps.core.services.operation_result import OperationResult
from apps.dms.field_mapping.services import field_mapping_persistence_service
from apps.dms.source_profile.services import source_persistence_service, version_publish_service
from apps.dms.target_profile.services import target_persistence_service
from apps.dms.transform_rules.services import transform_rules_persistence_service
from apps.projects.models import Project
from apps.reverse_studio.input.services.input_whitelist import (
    reject_non_whitelist_file_type as reject_input_type,
)
from apps.reverse_studio.input.services import input_wizard_service
from apps.reverse_studio.output.services.output_whitelist import (
    reject_auto_write_format,
    reject_non_whitelist_file_type as reject_output_type,
)
from apps.reverse_studio.output.services import output_wizard_service


@dataclass
class ChecklistItem:
    code: str
    label: str
    ready: bool
    detail: str
    url_name: str


@dataclass
class PublishHubContext:
    draft_version_number: int
    published_version_label: str
    published_version_number: int | None
    has_published_version: bool
    can_publish: bool
    checklist: list[ChecklistItem] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)


def _rewrite_publish_message(message: str) -> str:
    text = message or ""
    replacements = (
        ("perfil de origen", "contrato de entrada"),
        ("perfil de destino", "contrato de salida"),
        ("mapeo de campos", "mapeo"),
        ("origen", "entrada"),
        ("destino", "layout"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def get_checklist(project: Project, membership=None) -> list[ChecklistItem]:
    input_wizard = input_wizard_service.get_wizard_context(project, membership)
    output_wizard = output_wizard_service.get_wizard_context(project, membership)
    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)
    mappings_ok = field_mapping_persistence_service.is_mappings_complete(project)

    input_ready = (
        input_wizard.steps_complete >= input_wizard.steps_total
        and bool(source.get("fields"))
        and reject_input_type(source.get("file_type_code")) is None
        and bool((source.get("file_type_code") or "").strip())
    )
    output_ready = (
        output_wizard.steps_complete >= output_wizard.steps_total
        and bool(target.get("fields"))
        and reject_output_type(target.get("file_type_code")) is None
        and bool((target.get("file_type_code") or "").strip())
        and reject_auto_write_format(
            target.get("encoding_code"),
            target.get("line_ending_code"),
        )
        is None
    )

    mappings_data = field_mapping_persistence_service.get_mappings_dict(project)
    mappings = [m for m in (mappings_data.get("mappings") or []) if m.get("is_active", True)]
    pipe_errors, _ = transform_rules_persistence_service.validate_mappings_pipelines(
        mappings, strict=True
    )
    rules_ready = not pipe_errors

    items = [
        ChecklistItem(
            "input",
            "Entrada (planilla)",
            input_ready,
            (
                f"{input_wizard.file_type_label} · {input_wizard.fields_count} campos"
                if input_ready
                else f"{input_wizard.steps_complete}/{input_wizard.steps_total} pasos"
            ),
            "reverse_studio:input_hub",
        ),
        ChecklistItem(
            "output",
            "Salida (layout de envío)",
            output_ready,
            (
                f"{output_wizard.file_type_label} · {output_wizard.fields_count} campos"
                if output_ready
                else f"{output_wizard.steps_complete}/{output_wizard.steps_total} pasos"
            ),
            "reverse_studio:output_hub",
        ),
        ChecklistItem(
            "mapping",
            "Mapeo",
            mappings_ok,
            "Obligatorios del layout cubiertos" if mappings_ok else "Faltan enlaces obligatorios",
            "reverse_studio:mapping_hub",
        ),
        ChecklistItem(
            "rules",
            "Reglas",
            rules_ready,
            "Pipelines válidos" if rules_ready else "Hay reglas inválidas",
            "reverse_studio:mapping_rules_hub",
        ),
    ]
    return items


def get_hub_context(user, project: Project, membership=None) -> PublishHubContext:
    publish = version_publish_service.get_publish_context(project)
    checklist = get_checklist(project, membership)
    can_edit = source_persistence_service.user_can_edit_source(user, project)
    blocking = [item.label for item in checklist if not item.ready]
    can_publish = can_edit and not blocking
    return PublishHubContext(
        draft_version_number=publish["draft_version_number"],
        published_version_label=publish["published_version_label"],
        published_version_number=publish["published_version_number"],
        has_published_version=publish["has_published_version"],
        can_publish=can_publish,
        checklist=checklist,
        blocking_reasons=blocking,
    )


def _preflight_whitelist(project: Project) -> OperationResult | None:
    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)

    if not (source.get("file_type_code") or "").strip():
        return OperationResult.failure(
            "validation_form",
            "Complete el contrato de entrada antes de publicar.",
            errors={"file_type_code": ["Seleccione el tipo de planilla."]},
        )
    input_err = reject_input_type(source.get("file_type_code"))
    if input_err is not None:
        return input_err

    if not (target.get("file_type_code") or "").strip():
        return OperationResult.failure(
            "validation_form",
            "Complete el contrato de salida antes de publicar.",
            errors={"file_type_code": ["Seleccione el tipo de layout."]},
        )
    output_err = reject_output_type(target.get("file_type_code"))
    if output_err is not None:
        return output_err
    auto_err = reject_auto_write_format(
        target.get("encoding_code"),
        target.get("line_ending_code"),
    )
    if auto_err is not None:
        return auto_err

    mappings_data = field_mapping_persistence_service.get_mappings_dict(project)
    mappings = [m for m in (mappings_data.get("mappings") or []) if m.get("is_active", True)]
    pipe_errors, pipe_warnings = transform_rules_persistence_service.validate_mappings_pipelines(
        mappings, strict=True
    )
    if pipe_errors:
        return OperationResult.failure(
            "validation_form",
            "Corrija las reglas de transformación antes de publicar.",
            errors=pipe_errors,
            warnings=pipe_warnings,
        )
    return None


def publish_definition(user, project: Project) -> OperationResult:
    if project.project_kind != Project.KIND_REVERSE:
        return version_publish_service.publish_draft_version(user, project)

    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para publicar la definición de este proyecto.",
        )

    preflight = _preflight_whitelist(project)
    if preflight is not None:
        return preflight

    result = version_publish_service.publish_draft_version(user, project)
    if result.ok:
        payload = result.payload or {}
        published_n = payload.get("published_version_number")
        draft_n = payload.get("new_draft_version_number")
        return OperationResult.success(
            user_message=(
                f"Definición v{published_n} publicada correctamente. "
                f"Nuevo borrador v{draft_n} listo para edición."
            ),
            payload=payload,
        )

    return OperationResult.failure(
        result.error_code or "unexpected",
        _rewrite_publish_message(result.user_message or "No se pudo publicar."),
        errors=result.errors or {},
        **(result.payload or {}),
    )
