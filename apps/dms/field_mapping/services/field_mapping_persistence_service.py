"""Persistencia de mapeos FieldMapping sobre borrador DmsMappingVersion."""

import copy
import logging

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.field_mapping.models import DmsFieldMappingSet
from apps.dms.field_mapping.services.field_normalization_service import (
    ALL_KINDS,
    EXPRESSION_OPS,
    GENERATOR_TYPES,
    MVP_KINDS,
    SPLIT_PARTS,
    normalize_mappings_list,
)
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.services import target_persistence_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)


def _active_generator_codes() -> frozenset[str]:
    try:
        from apps.dms.models import ValueGeneratorType

        codes = list(
            ValueGeneratorType.objects.filter(is_active=True).values_list("code", flat=True)
        )
        if codes:
            return frozenset(codes)
    except Exception:
        pass
    return GENERATOR_TYPES


def default_mappings_dict() -> dict:
    return {"mappings": []}


def user_can_edit_mappings(user, project: Project) -> bool:
    return source_persistence_service.user_can_edit_source(user, project)


def set_to_dict(mapping_set: DmsFieldMappingSet) -> dict:
    return {
        "mappings": normalize_mappings_list(mapping_set.mappings or []),
    }


def apply_dict_to_set(mapping_set: DmsFieldMappingSet, data: dict) -> None:
    if "mappings" in data:
        mapping_set.mappings = normalize_mappings_list(data.get("mappings") or [])


def profile_defaults_from_dict(data: dict) -> dict:
    return {
        "mappings": normalize_mappings_list((data or {}).get("mappings") or []),
    }


def flatten_validation_messages(bucket: dict[str, list[str]] | None) -> list[str]:
    messages: list[str] = []
    for items in (bucket or {}).values():
        messages.extend(items)
    return messages


def ensure_mapping_set_on_version(version) -> DmsFieldMappingSet:
    mapping_set, _created = DmsFieldMappingSet.objects.get_or_create(
        version=version,
        defaults=profile_defaults_from_dict(default_mappings_dict()),
    )
    return mapping_set


def get_or_create_draft_with_mappings(project: Project):
    version = source_persistence_service.get_or_create_draft_version(project)
    target_persistence_service.ensure_target_on_version(version)
    ensure_mapping_set_on_version(version)
    return version


def get_mappings_dict(project: Project) -> dict:
    version = get_or_create_draft_with_mappings(project)
    return set_to_dict(version.field_mapping_set)


def suggest_direct_mappings(source_fields: list, target_fields: list) -> list[dict]:
    source_names = {
        (field.get("name") or "").strip().lower()
        for field in (source_fields or [])
        if (field.get("name") or "").strip()
    }
    suggestions = []
    for index, field in enumerate(target_fields or []):
        name = (field.get("name") or "").strip().lower()
        if not name or name not in source_names:
            continue
        suggestions.append(
            {
                "target_field": name,
                "mapping_kind": "direct",
                "source_fields": [name],
                "transform_pipeline": [{"op": "trim"}],
                "sort_order": index + 1,
                "is_active": True,
            }
        )
    return suggestions


def validate_mappings_dict(
    data: dict,
    *,
    source_fields: list,
    target_fields: list,
    strict: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    source_names = {
        (field.get("name") or "").strip().lower()
        for field in (source_fields or [])
        if (field.get("name") or "").strip()
    }
    target_by_name = {
        (field.get("name") or "").strip().lower(): field
        for field in (target_fields or [])
        if (field.get("name") or "").strip()
    }

    mappings = normalize_mappings_list((data or {}).get("mappings") or [])
    if strict and not mappings and target_fields:
        errors.setdefault("mappings", []).append("Defina al menos un mapeo para los campos destino.")

    seen_targets: set[str] = set()
    used_sources: set[str] = set()

    for mapping in mappings:
        if not mapping.get("is_active", True):
            continue
        target = mapping.get("target_field") or ""
        kind = mapping.get("mapping_kind") or ""

        if not target:
            errors.setdefault("mappings", []).append("Hay mapeos sin target_field.")
            continue
        if target not in target_by_name:
            errors.setdefault("mappings", []).append(
                f"Campo destino «{target}» no existe en el perfil de destino."
            )
        if target in seen_targets:
            errors.setdefault("mappings", []).append(
                f"Ya existe un mapeo activo para «{target}»."
            )
        seen_targets.add(target)

        if kind not in ALL_KINDS:
            errors.setdefault("mappings", []).append(
                f"Mapeo «{target}»: mapping_kind «{kind}» no válido."
            )
            continue
        if kind not in MVP_KINDS:
            continue

        for source_name in mapping.get("source_fields") or []:
            used_sources.add(source_name)
            if source_name not in source_names:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: campo origen «{source_name}» no existe."
                )

        if kind == "direct":
            if len(mapping.get("source_fields") or []) != 1:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: direct requiere exactamente un campo origen."
                )
        elif kind == "constant":
            if mapping.get("value") in (None, ""):
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: constant requiere value."
                )
        elif kind == "concat":
            parts = mapping.get("parts") or []
            if not parts:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: concat requiere parts."
                )
        elif kind == "generated":
            generator = mapping.get("generator") or {}
            gtype = (generator.get("type") or "").strip()
            allowed = _active_generator_codes()
            if not gtype:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: generated requiere generator.type."
                )
            elif gtype not in allowed:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: tipo de generador «{gtype}» no válido."
                )
        elif kind == "split":
            if len(mapping.get("source_fields") or []) != 1:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: split requiere exactamente un campo origen."
                )
            split = mapping.get("split") or {}
            part = (split.get("part") or "").strip()
            if part not in SPLIT_PARTS:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: split requiere una parte válida."
                )
            elif part == "delimiter" and split.get("delimiter") is None:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: split delimiter requiere delimiter."
                )
            elif part == "substring":
                if int(split.get("length") or 0) < 1:
                    errors.setdefault("mappings", []).append(
                        f"Mapeo «{target}»: split substring requiere length ≥ 1."
                    )
            elif part == "regex" and not str(split.get("pattern") or "").strip():
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: split regex requiere pattern."
                )
        elif kind == "expression":
            expression = mapping.get("expression") or {}
            op = (expression.get("op") or "").strip()
            if op not in EXPRESSION_OPS:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: expression requiere un operador válido."
                )
            elif "left" not in expression or "right" not in expression:
                errors.setdefault("mappings", []).append(
                    f"Mapeo «{target}»: expression requiere left y right."
                )

    for name, field in target_by_name.items():
        if name in seen_targets:
            continue
        required = bool(field.get("required"))
        has_default = field.get("default_value") not in (None, "")
        if required and not has_default:
            msg = f"Campo destino obligatorio «{name}» sin mapeo ni default_value."
            if strict:
                errors.setdefault("mappings", []).append(msg)
            else:
                warnings.setdefault("mappings", []).append(msg)
        else:
            warnings.setdefault("mappings", []).append(
                f"Campo destino «{name}» aún sin mapeo."
            )

    unused = source_names - used_sources
    for name in sorted(unused):
        warnings.setdefault("mappings", []).append(
            f"Campo origen «{name}» no se usa en ningún mapeo."
        )

    from apps.dms.transform_rules.services import transform_rules_persistence_service

    pipe_errors, pipe_warnings = transform_rules_persistence_service.validate_mappings_pipelines(
        mappings, strict=strict
    )
    for key, items in pipe_errors.items():
        errors.setdefault(key, []).extend(items)
    for key, items in pipe_warnings.items():
        warnings.setdefault(key, []).extend(items)

    return errors, warnings


@transaction.atomic
def save_mappings(
    user,
    project: Project,
    partial: dict,
    *,
    strict: bool = False,
) -> OperationResult:
    if not user_can_edit_mappings(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar el mapeo de campos.",
        )

    version = get_or_create_draft_with_mappings(project)
    mapping_set = version.field_mapping_set
    current = set_to_dict(mapping_set)
    merged = copy.deepcopy(current)
    if "mappings" in (partial or {}):
        merged["mappings"] = normalize_mappings_list(partial.get("mappings") or [])

    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)
    errors, warnings = validate_mappings_dict(
        merged,
        source_fields=source.get("fields") or [],
        target_fields=target.get("fields") or [],
        strict=strict,
    )
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del mapeo de campos.",
            errors=errors,
            warnings=warnings,
        )

    try:
        apply_dict_to_set(mapping_set, merged)
        mapping_set.save()
        version.save(update_fields=["updated_at"])
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("save_mappings unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Mapeo de campos guardado correctamente.",
        payload={
            "mappings": set_to_dict(mapping_set)["mappings"],
            "version": version,
            "warnings": warnings,
            "warning_messages": flatten_validation_messages(warnings),
        },
    )


def is_mappings_complete(project: Project) -> bool:
    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)
    data = get_mappings_dict(project)
    errors, _warnings = validate_mappings_dict(
        data,
        source_fields=source.get("fields") or [],
        target_fields=target.get("fields") or [],
        strict=True,
    )
    return not errors
