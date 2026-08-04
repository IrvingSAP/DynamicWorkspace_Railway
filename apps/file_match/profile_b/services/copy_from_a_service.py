"""Copiar estructura del Perfil A (borrador) al borrador del Perfil B."""

from __future__ import annotations

import logging

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.profile_b.services import profile_b_persistence_service
from apps.file_match.profile_b.services.profile_b_whitelist import (
    WHITELIST_REJECT_MESSAGE,
    reject_non_whitelist_file_type,
)
from apps.file_match.rules.services import match_rules_persistence_service
from apps.profile_seed.models import ProfileSeedEvent
from apps.profile_seed.services.apply_seed_service import (
    FIELD_NAMES_SAMPLE_LIMIT,
    map_published_source_to_partials,
)
from apps.projects.models import Project

logger = logging.getLogger(__name__)

MSG_COPY_OK = (
    "Estructura del Perfil A copiada al borrador del Perfil B. "
    "Revise B y configure las reglas de cruce cuando corresponda."
)
MSG_COPY_OK_WITH_RULES = (
    "Estructura del Perfil A copiada al borrador B y se propusieron pares 1:1 "
    "en Reglas (borrador). Revise clave y campos a comparar."
)
MSG_COPY_FAIL = (
    "No se pudo copiar la estructura desde el Perfil A. "
    "Si persiste, contacte al administrador."
)
MSG_A_INCOMPLETE = (
    "El Perfil A no tiene tipo de archivo y campos suficientes para copiar. "
    "Complete el Perfil A e intente de nuevo."
)
MSG_NO_PERMISSION = "No tiene permiso para editar el perfil B de este proyecto."

SOURCE_KIND_FILE_MATCH = "file_match"
SOURCE_SLOT_PROFILE_A = "profile_a"
TARGET_SLOT_PROFILE_B = "profile_b"


def user_can_copy_from_a(user, project: Project) -> bool:
    return source_persistence_service.user_can_edit_source(user, project)


def get_copy_from_a_hub_context(user, project: Project) -> dict:
    """Flags for Perfil B hub CTA."""
    can_edit = user_can_copy_from_a(user, project)
    source_a = source_persistence_service.get_source_dict(project)
    fields_a = source_a.get("fields") or []
    file_type = (source_a.get("file_type_code") or "").strip()
    a_ready = bool(file_type) and bool(fields_a)
    source_b = profile_b_persistence_service.get_source_b_dict(project)
    return {
        "can_copy_from_a": can_edit and a_ready,
        "copy_from_a_a_ready": a_ready,
        "copy_from_a_can_edit": can_edit,
        "copy_from_a_a_fields": len(fields_a),
        "copy_from_a_b_fields": len(source_b.get("fields") or []),
    }


def _field_names_sample(fields: list) -> list[str]:
    names = []
    for item in fields:
        name = (item.get("name") or "").strip()
        if name:
            names.append(name)
        if len(names) >= FIELD_NAMES_SAMPLE_LIMIT:
            break
    return names


def _delimiter_label(source: dict) -> str:
    config = source.get("config") or {}
    delim = config.get("delimiter")
    if delim is None or delim == "":
        return ""
    return str(delim)


def get_copy_preview(user, project: Project) -> dict | None:
    """Preview for confirm screen; None if user cannot edit."""
    if not user_can_copy_from_a(user, project):
        return None

    source_a = source_persistence_service.get_source_dict(project)
    fields = source_a.get("fields") or []
    file_type = (source_a.get("file_type_code") or "").strip()

    whitelist_result = reject_non_whitelist_file_type(file_type)
    whitelist_error = None
    if whitelist_result is not None and not whitelist_result.ok:
        whitelist_error = whitelist_result.user_message or WHITELIST_REJECT_MESSAGE

    source_b = profile_b_persistence_service.get_source_b_dict(project)
    b_field_count = len(source_b.get("fields") or [])
    version = source_persistence_service.get_or_create_draft_version(project)

    rules = match_rules_persistence_service.get_rules_dict(project)
    rules_key_empty = not (rules.get("key") or [])
    common_names = [
        (f.get("name") or "").strip()
        for f in fields
        if (f.get("name") or "").strip()
    ]
    # After copy, B names == A names; homonyms = all A field names.
    can_suggest_rules = rules_key_empty and len(common_names) >= 1

    can_apply = whitelist_error is None and bool(file_type) and bool(fields)

    return {
        "source": {
            "slot_label": "Perfil A (archivo A)",
            "file_type_code": file_type or "—",
            "encoding_code": source_a.get("encoding_code") or "",
            "delimiter": _delimiter_label(source_a),
            "fields_count": len(fields),
            "field_names_sample": _field_names_sample(fields),
            "version_label": f"Borrador v{version.version_number}",
        },
        "target": {
            "slot_label": "Perfil B (archivo B)",
            "field_count": b_field_count,
            "file_type_code": source_b.get("file_type_code") or "",
        },
        "overwrite": b_field_count > 0,
        "can_apply": can_apply,
        "whitelist_error": whitelist_error,
        "can_suggest_rules": can_suggest_rules,
        "homonym_count": len(common_names),
    }


def build_homonym_rules_partial(project: Project) -> dict | None:
    """
    Propose 1:1 pairs by matching field names after A→B clone.
    First common name → key; remaining → compare.
    """
    names_a = match_rules_persistence_service.field_names_a(project)
    names_b = set(match_rules_persistence_service.field_names_b(project))
    common = [n for n in names_a if n in names_b]
    if not common:
        return None
    return {
        "key": [{"a": common[0], "b": common[0]}],
        "compare": [{"a": n, "b": n} for n in common[1:]],
    }


def _record_event(
    *,
    user,
    project: Project,
    status: str,
    message: str,
    source_version: int,
) -> ProfileSeedEvent:
    return ProfileSeedEvent.objects.create(
        target_project=project,
        target_slot=TARGET_SLOT_PROFILE_B,
        source_project=project,
        source_kind=SOURCE_KIND_FILE_MATCH,
        source_slot=SOURCE_SLOT_PROFILE_A,
        source_version=source_version,
        source_slug=project.slug,
        status=status,
        message=message,
        mode=ProfileSeedEvent.MODE_CLONE_SNAPSHOT,
        created_by=user,
    )


@transaction.atomic
def apply_copy_from_a(
    user,
    project: Project,
    *,
    suggest_rules: bool = False,
) -> OperationResult:
    if not user_can_copy_from_a(user, project):
        return OperationResult.failure("forbidden", MSG_NO_PERMISSION)

    if project.project_kind != Project.KIND_FILE_MATCH:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE MATCH.",
        )

    version = source_persistence_service.get_or_create_draft_version(project)
    source_a = source_persistence_service.get_source_dict(project)
    # Strip match_side A so B persistence can stamp B.
    config = dict(source_a.get("config") or {})
    config.pop("match_side", None)
    config.pop("gate_policy", None)
    source_a = {**source_a, "config": config}

    file_type = (source_a.get("file_type_code") or "").strip()
    fields = source_a.get("fields") or []

    whitelist_result = reject_non_whitelist_file_type(file_type)
    if whitelist_result is not None and not whitelist_result.ok:
        msg = whitelist_result.user_message or WHITELIST_REJECT_MESSAGE
        _record_event(
            user=user,
            project=project,
            status=ProfileSeedEvent.STATUS_FAILED,
            message=msg,
            source_version=version.version_number,
        )
        return OperationResult.failure(
            whitelist_result.error_code or "validation_form",
            msg,
            errors=whitelist_result.errors,
        )

    if not file_type or not fields:
        _record_event(
            user=user,
            project=project,
            status=ProfileSeedEvent.STATUS_FAILED,
            message=MSG_A_INCOMPLETE,
            source_version=version.version_number,
        )
        return OperationResult.failure("validation_form", MSG_A_INCOMPLETE)

    meta, fields_partial = map_published_source_to_partials(source_a)

    try:
        result_meta = profile_b_persistence_service.save_source_b(
            user, project, meta, strict=False
        )
        if not result_meta.ok:
            _record_event(
                user=user,
                project=project,
                status=ProfileSeedEvent.STATUS_FAILED,
                message=result_meta.user_message or MSG_COPY_FAIL,
                source_version=version.version_number,
            )
            return OperationResult.failure(
                result_meta.error_code or "unexpected",
                result_meta.user_message or MSG_COPY_FAIL,
                errors=result_meta.errors,
            )

        result_fields = profile_b_persistence_service.save_source_b(
            user, project, fields_partial, strict=False
        )
        if not result_fields.ok:
            _record_event(
                user=user,
                project=project,
                status=ProfileSeedEvent.STATUS_FAILED,
                message=result_fields.user_message or MSG_COPY_FAIL,
                source_version=version.version_number,
            )
            return OperationResult.failure(
                result_fields.error_code or "unexpected",
                result_fields.user_message or MSG_COPY_FAIL,
                errors=result_fields.errors,
            )
    except Exception:
        logger.exception("apply_copy_from_a unexpected project=%s", project.slug)
        _record_event(
            user=user,
            project=project,
            status=ProfileSeedEvent.STATUS_FAILED,
            message=MSG_COPY_FAIL,
            source_version=version.version_number,
        )
        return OperationResult.failure("unexpected", MSG_COPY_FAIL)

    rules_suggested = False
    if suggest_rules:
        current_rules = match_rules_persistence_service.get_rules_dict(project)
        if not (current_rules.get("key") or []):
            partial = build_homonym_rules_partial(project)
            if partial:
                rules_result = match_rules_persistence_service.save_rules(
                    user, project, partial, strict=False
                )
                rules_suggested = bool(rules_result.ok)

    ok_message = MSG_COPY_OK_WITH_RULES if rules_suggested else MSG_COPY_OK
    event = _record_event(
        user=user,
        project=project,
        status=ProfileSeedEvent.STATUS_OK,
        message=ok_message,
        source_version=version.version_number,
    )
    project.save(update_fields=["updated_at"])
    return OperationResult.success(
        user_message=ok_message,
        payload={
            "event_id": str(event.id),
            "rules_suggested": rules_suggested,
        },
    )
