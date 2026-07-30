"""Persistencia del SourceProfile lado B (FileMatchSourceB)."""

from __future__ import annotations

import logging

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.models import FileMatchSourceB
from apps.file_match.profile_b.services.profile_b_whitelist import (
    reject_non_whitelist_file_type,
)
from apps.projects.models import Project

logger = logging.getLogger(__name__)


def profile_to_dict(profile: FileMatchSourceB) -> dict:
    from apps.dms.source_profile.services.field_normalization_service import flatten_field_for_edit
    from apps.dms.transform_execution.services.capture_params import normalize_capture

    fields = [flatten_field_for_edit(item) for item in (profile.fields or [])]
    config = profile.config or {}
    return {
        "file_type_code": profile.file_type_code,
        "encoding_code": config.get("encoding_code") or "",
        "encoding_custom": config.get("encoding_custom"),
        "line_ending_code": config.get("line_ending_code") or "",
        "line_ending_custom": config.get("line_ending_custom"),
        "capture_start": normalize_capture(profile.capture_start or {}),
        "capture_end": normalize_capture(profile.capture_end or {}),
        "content_rules": profile.content_rules or {},
        "processing_report": profile.processing_report or {},
        "fields": fields,
        "config": config,
    }


def apply_dict_to_profile(profile: FileMatchSourceB, data: dict) -> None:
    if "file_type_code" in data:
        profile.file_type_code = (data.get("file_type_code") or "").strip()
    if "capture_start" in data:
        profile.capture_start = data["capture_start"] or {}
    if "capture_end" in data:
        profile.capture_end = data["capture_end"] or {}
    if "content_rules" in data:
        profile.content_rules = data["content_rules"] or {}
    if "processing_report" in data:
        profile.processing_report = data["processing_report"] or {}
    if "fields" in data:
        profile.fields = data["fields"] or []
    if "config" in data:
        profile.config = data["config"] or {}

    config = dict(profile.config or {})
    for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
        if key in data:
            value = data[key]
            if value is None or value == "":
                config.pop(key, None)
            else:
                config[key] = value
    config["match_side"] = "B"
    profile.config = config


def get_or_create_source_b(project: Project) -> FileMatchSourceB:
    version = source_persistence_service.get_or_create_draft_version(project)
    defaults = source_persistence_service.profile_defaults_from_dict(
        source_persistence_service.default_source_dict()
    )
    defaults["config"] = {**(defaults.get("config") or {}), "match_side": "B"}
    profile, _created = FileMatchSourceB.objects.get_or_create(
        version=version,
        defaults=defaults,
    )
    return profile


def get_source_b_dict(project: Project) -> dict:
    return profile_to_dict(get_or_create_source_b(project))


def ensure_step4_coherence_b(project: Project) -> dict:
    from apps.dms.source_profile.services.source_profile_service import (
        default_config_for_type,
        get_step4_variant,
    )

    profile = get_or_create_source_b(project)
    source = profile_to_dict(profile)
    file_type = source.get("file_type_code", "")
    variant = get_step4_variant(file_type)
    if variant == "unsupported" or not file_type:
        return source

    fields = source.get("fields") or []
    config = source.get("config") or {}
    typed_config = default_config_for_type(file_type, config)
    typed_config["match_side"] = "B"
    if typed_config != config and not fields:
        profile.config = typed_config
        profile.save(update_fields=["config", "updated_at"])
        return profile_to_dict(profile)
    return source


def save_source_b(user, project: Project, partial: dict, *, strict: bool = False) -> OperationResult:
    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar el contrato de este proyecto.",
        )
    if project.project_kind != Project.KIND_FILE_MATCH:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE MATCH.",
        )

    profile = get_or_create_source_b(project)
    current = profile_to_dict(profile)
    merged = source_persistence_service.merge_source_dict(current, partial)

    whitelist_error = reject_non_whitelist_file_type(merged.get("file_type_code"))
    if whitelist_error is not None:
        return whitelist_error

    config = dict(merged.get("config") or {})
    config["match_side"] = "B"
    merged["config"] = config

    new_type = (merged.get("file_type_code") or "").strip()
    old_type = (current.get("file_type_code") or "").strip()
    if new_type and new_type != old_type:
        from apps.dms.source_profile.services.source_profile_service import (
            default_config_for_type,
        )

        merged["fields"] = []
        preserved_config = dict(merged.get("config") or {})
        for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
            value = preserved_config.get(key) or merged.get(key) or current.get(key)
            if value:
                preserved_config[key] = value
        preserved_config["match_side"] = "B"
        merged["config"] = default_config_for_type(new_type, preserved_config)

    from apps.dms.source_profile.services.field_normalization_service import normalize_fields_list

    merged["fields"] = normalize_fields_list(
        merged.get("fields") or [],
        merged.get("file_type_code") or "",
    )

    errors, warnings = source_persistence_service.validate_source_dict(merged, strict=strict)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del perfil B.",
            errors=errors,
            warnings=warnings,
        )

    try:
        apply_dict_to_profile(profile, merged)
        profile.save()
        profile.version.save(update_fields=["updated_at"])
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("save_source_b unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Perfil B guardado correctamente.",
        payload={
            "source": profile_to_dict(profile),
            "version": profile.version,
            "warnings": warnings,
            "warning_messages": source_persistence_service.flatten_validation_messages(
                warnings
            ),
        },
    )
