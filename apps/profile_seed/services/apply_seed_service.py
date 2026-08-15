"""PROFILE_SEED — preview y apply borrador (Match Perfil A + Split/Merge)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
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
MSG_APPLY_OK_DMS = (
    "Estructura importada al borrador de la definición de origen. "
    "Revise los pasos del asistente y publique FilePipe cuando corresponda."
)
MSG_APPLY_OK_DMS_TARGET = (
    "Estructura importada al borrador de la definición de destino. "
    "Revise layout, serialización y publique FilePipe cuando corresponda."
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
MSG_TYPE_UNSUPPORTED_DMS = (
    "El tipo de archivo seleccionado aún no tiene editor de campos en "
    "FilePipe. Elija txt_fixed, csv, txt_delimited, xlsx, json o xml."
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


def map_published_source_to_target_partial(source: dict) -> dict | OperationResult:
    """Adapt a published read-profile snapshot into TargetProfile save_target partial."""
    from apps.dms.target_profile.services import import_source_fields_service, target_profile_service

    source = _clean_published_source(source)
    file_type = (source.get("file_type_code") or "").strip()
    built = import_source_fields_service.build_fields_from_source_snapshot(
        source, file_type
    )
    if not built.ok:
        return built

    layout = target_profile_service.default_layout_for_type(file_type)
    config = source.get("config") or {}
    if config.get("delimiter"):
        layout["delimiter"] = config["delimiter"]
    if config.get("quote_char"):
        layout["quote_char"] = config["quote_char"]
    if "has_header" in config:
        layout["include_header"] = bool(config.get("has_header"))
    if config.get("sheet_name"):
        layout["sheet_name"] = config["sheet_name"]
    records_path = config.get("records_path") or config.get("record_path")
    if records_path:
        layout["records_path"] = records_path
    if config.get("record_element"):
        layout["record_element"] = config["record_element"]
    if config.get("root_element"):
        layout["root_element"] = config["root_element"]

    return {
        "file_type_code": file_type,
        "encoding_code": source.get("encoding_code") or "",
        "encoding_custom": source.get("encoding_custom"),
        "line_ending_code": source.get("line_ending_code") or "",
        "line_ending_custom": source.get("line_ending_custom"),
        "layout": layout,
        "fields": list(built.payload.get("fields") or []),
        "serialization": dict(target_profile_service.DEFAULT_SERIALIZATION),
        "write_validation": dict(target_profile_service.DEFAULT_WRITE_VALIDATION),
    }


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


def _load_scout_draft_source(source_project: Project) -> tuple[object | None, dict]:
    from apps.structure_scout.apply.services import apply_target_service
    from apps.structure_scout.draft.services import save_draft_service

    draft = save_draft_service.get_current_draft(source_project)
    if draft is None:
        return None, {}
    raw_src = (draft.payload or {}).get("source") or {}
    if not (raw_src.get("file_type_code") or "").strip():
        return None, {}
    meta, fields_partial = apply_target_service.map_scout_source_to_partials(raw_src)
    combined = {**meta, **fields_partial}
    published = SimpleNamespace(
        version_number=draft.version,
        published_at=draft.created_at,
    )
    return published, _clean_published_source(combined)


def _load_published_source(
    source_project: Project, *, source_kind: str | None = None
) -> tuple[object | None, dict]:
    if (
        source_kind == profile_seed_service.SOURCE_KIND_SCOUT
        or source_project.project_kind == Project.KIND_STRUCTURE_SCOUT
    ):
        return _load_scout_draft_source(source_project)
    published = file_intake_persistence_service.get_published_version(source_project)
    if published is None:
        return None, {}
    if source_kind == profile_seed_service.SOURCE_KIND_FILE_MATCH_B:
        from apps.file_match.models import FileMatchSourceB
        from apps.file_match.profile_b.services import profile_b_persistence_service

        try:
            profile_b = published.match_source_b
        except FileMatchSourceB.DoesNotExist:
            return None, {}
        raw = profile_b_persistence_service.profile_to_dict(profile_b)
        return published, _clean_published_source(raw)
    if published.source_profile is None:
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


def _source_meta_for_project(
    source_project: Project, published, *, source_kind: str | None = None
) -> dict:
    if source_kind == profile_seed_service.SOURCE_KIND_FILE_MATCH_B:
        return {
            "kind": profile_seed_service.SOURCE_KIND_FILE_MATCH_B,
            "kind_label": "FILE MATCH",
            "slot": profile_seed_service.SOURCE_SLOT_PROFILE_B,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_PROFILE_B,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    if source_project.project_kind == Project.KIND_FILE_CLEAN:
        return {
            "kind": profile_seed_service.SOURCE_KIND_FILE_CLEAN,
            "kind_label": "FILE CLEAN",
            "slot": profile_seed_service.SOURCE_SLOT_READ_PROFILE,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_READ_PROFILE,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    if source_project.project_kind == Project.KIND_DMS:
        return {
            "kind": profile_seed_service.SOURCE_KIND_DMS,
            "kind_label": "FilePipe",
            "slot": profile_seed_service.SOURCE_SLOT_SOURCE,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_DMS_SOURCE,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    if source_project.project_kind == Project.KIND_FILE_MATCH:
        return {
            "kind": profile_seed_service.SOURCE_KIND_FILE_MATCH,
            "kind_label": "FILE MATCH",
            "slot": profile_seed_service.SOURCE_SLOT_PROFILE_A,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_PROFILE_A,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    if source_project.project_kind == Project.KIND_REVERSE:
        return {
            "kind": profile_seed_service.SOURCE_KIND_REVERSE,
            "kind_label": "Reverse Studio",
            "slot": profile_seed_service.SOURCE_SLOT_INPUT,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_INPUT,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    if source_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return {
            "kind": profile_seed_service.SOURCE_KIND_SPLIT_MERGE,
            "kind_label": "FILE SPLIT/MERGE",
            "slot": profile_seed_service.SOURCE_SLOT_READ_PROFILE,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_READ_PROFILE,
            "version": published.version_number,
            "slug": source_project.slug,
        }
    if source_project.project_kind == Project.KIND_STRUCTURE_SCOUT:
        return {
            "kind": profile_seed_service.SOURCE_KIND_SCOUT,
            "kind_label": "STRUCTURE SCOUT",
            "slot": profile_seed_service.SOURCE_SLOT_DRAFT,
            "slot_label": profile_seed_service.SOURCE_SLOT_LABEL_DRAFT,
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


def _target_meta(
    target_project: Project, destination_slot: str | None = None
) -> dict:
    _, slot, slot_label, _ = profile_seed_service._target_slot_meta(
        target_project, destination_slot
    )
    return {"slot": slot, "slot_label": slot_label}


def _apply_ok_message(
    target_project: Project, destination_slot: str | None = None
) -> str:
    slot = (destination_slot or "").strip()
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return MSG_APPLY_OK_SPLIT_MERGE
    if (
        target_project.project_kind == Project.KIND_DMS
        and slot == profile_seed_service.TARGET_SLOT_TARGET
    ):
        return MSG_APPLY_OK_DMS_TARGET
    if target_project.project_kind == Project.KIND_DMS:
        return MSG_APPLY_OK_DMS
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
    if target_project.project_kind == Project.KIND_DMS:
        variant = get_step4_variant(file_type)
        if variant == "unsupported" or not file_type:
            return OperationResult.failure("validation_form", MSG_TYPE_UNSUPPORTED_DMS)
        return None
    return None


def get_apply_preview(
    user,
    target_project: Project,
    source_id: UUID | None,
    *,
    destination_slot: str | None = None,
    source_kind: str | None = None,
) -> dict | None:
    """Preview context for confirm screen; None if source not eligible."""
    if not profile_seed_service.user_can_import(user, target_project):
        return None

    source_project = _resolve_source_project(
        user, target_project, source_id, source_kind=source_kind
    )
    if source_project is None:
        return None

    published, source = _load_published_source(
        source_project, source_kind=source_kind
    )
    if published is None:
        return None

    fields = source.get("fields") or []
    file_type = (source.get("file_type_code") or "").strip()
    type_check = _check_file_type_for_target(target_project, file_type)
    whitelist_error = None
    if type_check is not None and not type_check.ok:
        whitelist_error = type_check.user_message

    slot = (destination_slot or "").strip()
    if (
        target_project.project_kind == Project.KIND_DMS
        and slot == profile_seed_service.TARGET_SLOT_TARGET
    ):
        from apps.dms.target_profile.services import target_persistence_service

        target_current = target_persistence_service.get_target_dict(target_project)
    else:
        target_current = source_persistence_service.get_source_dict(target_project)
    target_field_count = len(target_current.get("fields") or [])
    source_meta = _source_meta_for_project(
        source_project, published, source_kind=source_kind
    )
    target_meta = _target_meta(target_project, destination_slot)

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
        "seed_host": profile_seed_service.get_seed_host(
            target_project, destination_slot=destination_slot
        ),
        **profile_seed_service.get_seed_context(
            user, target_project, destination_slot=destination_slot
        ),
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
    destination_slot: str | None = None,
) -> ProfileSeedEvent:
    target_meta = _target_meta(target_project, destination_slot)
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
    destination_slot: str | None = None,
    source_kind: str | None = None,
) -> OperationResult:
    """Clone published Gate/Clean (etc.) structure into destination draft."""
    if not profile_seed_service.user_can_import(user, target_project):
        return OperationResult.failure("forbidden", profile_seed_service.MSG_NO_IMPORT)

    if source_id is None:
        return OperationResult.failure("validation_form", MSG_NO_SOURCE_ID)

    source_project = _resolve_source_project(
        user, target_project, source_id, source_kind=source_kind
    )
    if source_project is None:
        return OperationResult.failure(
            "validation_form", profile_seed_service.MSG_SOURCE_UNAVAILABLE
        )

    published, source = _load_published_source(
        source_project, source_kind=source_kind
    )
    if published is None:
        return OperationResult.failure(
            "validation_form", profile_seed_service.MSG_SOURCE_UNAVAILABLE
        )

    file_type = (source.get("file_type_code") or "").strip()
    fields = source.get("fields") or []
    source_meta = _source_meta_for_project(
        source_project, published, source_kind=source_kind
    )
    ok_msg = _apply_ok_message(target_project, destination_slot)
    slot = (destination_slot or "").strip()
    seed_target = (
        target_project.project_kind == Project.KIND_DMS
        and slot == profile_seed_service.TARGET_SLOT_TARGET
    )

    def _fail_event(msg, code="validation_form", errors=None):
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
            destination_slot=destination_slot,
        )
        return OperationResult.failure(code, msg, errors=errors)

    type_check = _check_file_type_for_target(target_project, file_type)
    if type_check is not None and not type_check.ok:
        msg = type_check.user_message or MSG_APPLY_FAIL
        return _fail_event(
            msg, type_check.error_code or "validation_form", type_check.errors
        )

    if not file_type or not fields:
        return _fail_event(MSG_APPLY_FAIL, "unexpected")

    try:
        if seed_target:
            from apps.dms.target_profile.services import target_persistence_service

            mapped = map_published_source_to_target_partial(source)
            if isinstance(mapped, OperationResult):
                return _fail_event(
                    mapped.user_message or MSG_APPLY_FAIL,
                    mapped.error_code or "validation_form",
                    mapped.errors,
                )
            result = target_persistence_service.save_target(
                user, target_project, mapped, strict=False
            )
            if not result.ok:
                return _fail_event(
                    result.user_message or MSG_APPLY_FAIL,
                    result.error_code or "unexpected",
                    result.errors,
                )
        else:
            meta, fields_partial = map_published_source_to_partials(source)
            result_meta = source_persistence_service.save_source(
                user, target_project, meta, strict=False
            )
            if not result_meta.ok:
                return _fail_event(
                    result_meta.user_message or MSG_APPLY_FAIL,
                    result_meta.error_code or "unexpected",
                    result_meta.errors,
                )
            result_fields = source_persistence_service.save_source(
                user, target_project, fields_partial, strict=False
            )
            if not result_fields.ok:
                return _fail_event(
                    result_fields.user_message or MSG_APPLY_FAIL,
                    result_fields.error_code or "unexpected",
                    result_fields.errors,
                )
    except Exception:
        logger.exception(
            "apply_seed_to_draft unexpected target=%s source=%s",
            target_project.slug,
            source_project.slug,
        )
        return _fail_event(MSG_APPLY_FAIL, "unexpected")

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
        destination_slot=destination_slot,
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
