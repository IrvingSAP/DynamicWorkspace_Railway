"""PROFILE_SEED — preview y apply borrador (Match Perfil A + Split/Merge)."""

from __future__ import annotations

import logging
from uuid import UUID

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.services import file_intake_persistence_service
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.source_profile.services.source_profile_service import get_step4_variant
from apps.file_match.profile_a.services.profile_a_whitelist import (
    WHITELIST_REJECT_MESSAGE,
    reject_non_whitelist_file_type,
)
from apps.profile_seed.models import ProfileSeedEvent
from apps.profile_seed.services import profile_seed_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)

MSG_APPLY_OK_MATCH = (
    "Estructura importada al borrador del Perfil A. "
    "Revise y publique la definición Match cuando corresponda."
)
MSG_APPLY_OK_SPLIT_MERGE = (
    "Estructura importada al borrador del perfil de lectura. "
    "Revise los pasos del wizard y continue con reglas Split/Merge cuando corresponda."
)
MSG_APPLY_OK = MSG_APPLY_OK_MATCH  # compat
MSG_APPLY_FAIL = (
    "No se pudo importar la estructura. Si persiste, contacte al administrador."
)
MSG_NO_SOURCE_ID = "Seleccione un origen publicado antes de confirmar."
MSG_TYPE_UNSUPPORTED_SM = (
    "El tipo de archivo seleccionado aún no tiene editor de campos en "
    "File Split/Merge. Elija txt_fixed, csv, txt_delimited, xlsx, json o xml."
)

FIELD_NAMES_SAMPLE_LIMIT = 8


def _clean_published_source(raw: dict) -> dict:
    """Clone snapshot without app-specific policies / live links (PS1 / PS7)."""
    source = dict(raw or {})
    config = dict(source.get("config") or {})
    for key in ("gate_policy", "clean_rules", "match_side", "sm_rules", "split_merge_rules"):
        config.pop(key, None)
    source["config"] = config
    return source


def map_published_source_to_partials(source: dict) -> tuple[dict, dict]:
    """Build (meta_partial, fields_partial) for two-step save_source."""
    source = _clean_published_source(source)
    meta = {
        "file_type_code": source.get("file_type_code") or "",
        "encoding_code": source.get("encoding_code") or "",
        "encoding_custom": source.get("encoding_custom"),
        "line_ending_code": source.get("line_ending_code") or "",
        "line_ending_custom": source.get("line_ending_custom"),
        "capture_start": source.get("capture_start") or {},
        "capture_end": source.get("capture_end") or {},
        "content_rules": source.get("content_rules") or {},
        "processing_report": source.get("processing_report") or {},
        "config": dict(source.get("config") or {}),
    }
    fields = list(source.get("fields") or [])
    return meta, {"fields": fields}


def _resolve_source_project(
    user,
    target_project: Project,
    source_id: UUID | None,
    *,
    source_kind: str | None = None,
) -> Project | None:
    if source_id is None:
        return None
    kinds = []
    if source_kind:
        kinds = [source_kind]
    else:
        kinds = [
            code
            for code, _ in profile_seed_service._source_kind_choices_for(target_project)
        ]
    for kind in kinds:
        rows = profile_seed_service.list_eligible_sources(
            user, target_project, source_kind=kind
        )
        if any(row["id"] == source_id for row in rows):
            try:
                return Project.objects.get(pk=source_id, is_archived=False)
            except Project.DoesNotExist:
                return None
    return None


def _load_published_source(source_project: Project) -> tuple[object | None, dict]:
    published = file_intake_persistence_service.get_published_version(source_project)
    if published is None or published.source_profile is None:
        return None, {}
    raw = source_persistence_service.profile_to_dict(published.source_profile)
    return published, _clean_published_source(raw)


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


def _source_meta_for_project(source_project: Project, published) -> dict:
    if source_project.project_kind == Project.KIND_FILE_CLEAN:
        return {
            "kind": profile_seed_service.SOURCE_KIND_FILE_CLEAN,
            "kind_label": "FILE CLEAN",
            "slot": profile_seed_service.SOURCE_SLOT_READ_PROFILE,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_READ_PROFILE,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    return {
        "kind": profile_seed_service.SOURCE_KIND_FILE_GATE,
        "kind_label": "FILE GATE",
        "slot": profile_seed_service.SOURCE_SLOT_SCHEMA,
        "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_SCHEMA,
        "version": published.version_number,
        "slug": source_project.slug,
    }


def _target_meta(target_project: Project) -> dict:
    _, slot, slot_label, _ = profile_seed_service._target_slot_meta(target_project)
    return {"slot": slot, "slot_label": slot_label}


def _apply_ok_message(target_project: Project) -> str:
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return MSG_APPLY_OK_SPLIT_MERGE
    return MSG_APPLY_OK_MATCH


def _check_file_type_for_target(
    target_project: Project, file_type: str
) -> OperationResult | None:
    """Return failure OperationResult if type rejected; None if OK."""
    if target_project.project_kind == Project.KIND_FILE_MATCH:
        whitelist_result = reject_non_whitelist_file_type(file_type)
        if whitelist_result is not None and not whitelist_result.ok:
            return whitelist_result
        return None
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        variant = get_step4_variant(file_type)
        if variant == "unsupported" or not file_type:
            return OperationResult.failure("validation_form", MSG_TYPE_UNSUPPORTED_SM)
        return None
    return None


def get_apply_preview(
    user, target_project: Project, source_id: UUID | None
) -> dict | None:
    """Preview context for confirm screen; None if source not eligible."""
    if not profile_seed_service.user_can_import(user, target_project):
        return None

    source_project = _resolve_source_project(user, target_project, source_id)
    if source_project is None:
        return None

    published, source = _load_published_source(source_project)
    if published is None:
        return None

    fields = source.get("fields") or []
    file_type = (source.get("file_type_code") or "").strip()
    type_check = _check_file_type_for_target(target_project, file_type)
    whitelist_error = None
    if type_check is not None and not type_check.ok:
        whitelist_error = type_check.user_message

    target_current = source_persistence_service.get_source_dict(target_project)
    target_field_count = len(target_current.get("fields") or [])
    source_meta = _source_meta_for_project(source_project, published)
    target_meta = _target_meta(target_project)

    source_row = {
        "id": source_project.id,
        "slug": source_project.slug,
        "name": source_project.name,
        "kind": source_meta["kind"],
        "kind_label": source_meta["kind_label"],
        "slot": source_meta["slot"],
        "slot_label": source_meta["slot_label"],
        "version_number": published.version_number,
        "version_label": f"v{published.version_number}",
        "file_type_code": file_type or "—",
        "fields_count": len(fields),
        "published_at": published.published_at,
        "encoding_code": source.get("encoding_code") or "",
        "delimiter": _delimiter_label(source),
        "field_names_sample": _field_names_sample(fields),
    }
    target_info = {
        "slug": target_project.slug,
        "name": target_project.name,
        "slot": target_meta["slot"],
        "slot_label": target_meta["slot_label"],
        "field_count": target_field_count,
        "file_type_code": target_current.get("file_type_code") or "",
    }
    can_apply = whitelist_error is None and bool(file_type) and bool(fields)

    return {
        "source": source_row,
        "target": target_info,
        "overwrite": target_field_count > 0,
        "can_apply": can_apply,
        "whitelist_error": whitelist_error,
        "seed_step": 3,
        "seed_steps_total": 3,
        "seed_host": profile_seed_service.get_seed_host(target_project),
        **profile_seed_service.get_seed_context(user, target_project),
    }


def _record_event(
    *,
    user,
    target_project: Project,
    source_project: Project | None,
    source_kind: str,
    source_slot: str,
    source_version: int,
    source_slug: str,
    status: str,
    message: str,
) -> ProfileSeedEvent:
    target_meta = _target_meta(target_project)
    return ProfileSeedEvent.objects.create(
        target_project=target_project,
        target_slot=target_meta["slot"],
        source_project=source_project,
        source_kind=source_kind,
        source_slot=source_slot,
        source_version=source_version,
        source_slug=source_slug,
        status=status,
        message=message,
        mode=ProfileSeedEvent.MODE_CLONE_SNAPSHOT,
        created_by=user,
    )


@transaction.atomic
def apply_seed_to_draft(
    user,
    target_project: Project,
    *,
    source_id: UUID | None,
) -> OperationResult:
    """Clone published Gate/Clean (etc.) structure into destination draft."""
    if not profile_seed_service.user_can_import(user, target_project):
        return OperationResult.failure("forbidden", profile_seed_service.MSG_NO_IMPORT)

    if source_id is None:
        return OperationResult.failure("validation_form", MSG_NO_SOURCE_ID)

    source_project = _resolve_source_project(user, target_project, source_id)
    if source_project is None:
        return OperationResult.failure(
            "validation_form", profile_seed_service.MSG_SOURCE_UNAVAILABLE
        )

    published, source = _load_published_source(source_project)
    if published is None:
        return OperationResult.failure(
            "validation_form", profile_seed_service.MSG_SOURCE_UNAVAILABLE
        )

    file_type = (source.get("file_type_code") or "").strip()
    fields = source.get("fields") or []
    source_meta = _source_meta_for_project(source_project, published)
    ok_msg = _apply_ok_message(target_project)

    type_check = _check_file_type_for_target(target_project, file_type)
    if type_check is not None and not type_check.ok:
        msg = type_check.user_message or MSG_APPLY_FAIL
        _record_event(
            user=user,
            target_project=target_project,
            source_project=source_project,
            source_kind=source_meta["kind"],
            source_slot=source_meta["slot"],
            source_version=source_meta["version"],
            source_slug=source_meta["slug"],
            status=ProfileSeedEvent.STATUS_FAILED,
            message=msg,
        )
        return OperationResult.failure(
            type_check.error_code or "validation_form",
            msg,
            errors=type_check.errors,
        )

    if not file_type or not fields:
        _record_event(
            user=user,
            target_project=target_project,
            source_project=source_project,
            source_kind=source_meta["kind"],
            source_slot=source_meta["slot"],
            source_version=source_meta["version"],
            source_slug=source_meta["slug"],
            status=ProfileSeedEvent.STATUS_FAILED,
            message=MSG_APPLY_FAIL,
        )
        return OperationResult.failure("unexpected", MSG_APPLY_FAIL)

    meta, fields_partial = map_published_source_to_partials(source)

    try:
        result_meta = source_persistence_service.save_source(
            user, target_project, meta, strict=False
        )
        if not result_meta.ok:
            _record_event(
                user=user,
                target_project=target_project,
                source_project=source_project,
                source_kind=source_meta["kind"],
                source_slot=source_meta["slot"],
                source_version=source_meta["version"],
                source_slug=source_meta["slug"],
                status=ProfileSeedEvent.STATUS_FAILED,
                message=result_meta.user_message or MSG_APPLY_FAIL,
            )
            return OperationResult.failure(
                result_meta.error_code or "unexpected",
                result_meta.user_message or MSG_APPLY_FAIL,
                errors=result_meta.errors,
            )

        result_fields = source_persistence_service.save_source(
            user, target_project, fields_partial, strict=False
        )
        if not result_fields.ok:
            _record_event(
                user=user,
                target_project=target_project,
                source_project=source_project,
                source_kind=source_meta["kind"],
                source_slot=source_meta["slot"],
                source_version=source_meta["version"],
                source_slug=source_meta["slug"],
                status=ProfileSeedEvent.STATUS_FAILED,
                message=result_fields.user_message or MSG_APPLY_FAIL,
            )
            return OperationResult.failure(
                result_fields.error_code or "unexpected",
                result_fields.user_message or MSG_APPLY_FAIL,
                errors=result_fields.errors,
            )
    except Exception:
        logger.exception(
            "apply_seed_to_draft unexpected target=%s source=%s",
            target_project.slug,
            source_project.slug,
        )
        _record_event(
            user=user,
            target_project=target_project,
            source_project=source_project,
            source_kind=source_meta["kind"],
            source_slot=source_meta["slot"],
            source_version=source_meta["version"],
            source_slug=source_meta["slug"],
            status=ProfileSeedEvent.STATUS_FAILED,
            message=MSG_APPLY_FAIL,
        )
        return OperationResult.failure("unexpected", MSG_APPLY_FAIL)

    event = _record_event(
        user=user,
        target_project=target_project,
        source_project=source_project,
        source_kind=source_meta["kind"],
        source_slot=source_meta["slot"],
        source_version=source_meta["version"],
        source_slug=source_meta["slug"],
        status=ProfileSeedEvent.STATUS_OK,
        message=ok_msg,
    )
    target_project.save(update_fields=["updated_at"])
    return OperationResult.success(
        user_message=ok_msg,
        payload={"event_id": str(event.id)},
    )


def apply_seed_to_profile_a(
    user,
    target_project: Project,
    *,
    source_id: UUID | None,
) -> OperationResult:
    """Compat wrapper — Match Perfil A."""
    return apply_seed_to_draft(user, target_project, source_id=source_id)


def apply_seed_to_split_merge(
    user,
    target_project: Project,
    *,
    source_id: UUID | None,
) -> OperationResult:
    return apply_seed_to_draft(user, target_project, source_id=source_id)
