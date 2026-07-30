"""Publicar definición FILE MATCH (publish.md Módulo 4)."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.mapping.models import DmsProjectConfig
from apps.dms.source_profile.models import DmsMappingVersion, DmsSourceProfile
from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.models import FileMatchRules, FileMatchSourceB
from apps.file_match.profile_a.services import profile_a_wizard_service
from apps.file_match.profile_a.services.profile_a_whitelist import (
    reject_non_whitelist_file_type as reject_a_type,
)
from apps.file_match.profile_b.services import profile_b_persistence_service, profile_b_wizard_service
from apps.file_match.profile_b.services.profile_b_whitelist import (
    reject_non_whitelist_file_type as reject_b_type,
)
from apps.file_match.rules.services import match_rules_persistence_service, match_rules_wizard_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)


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


def get_publish_context(project: Project) -> dict:
    draft = source_persistence_service.get_draft_version(project)
    config = getattr(project, "dms_config", None)
    published = None
    if config is not None and config.current_version_id:
        published = config.current_version

    return {
        "draft_version_number": draft.version_number,
        "draft_version_id": str(draft.id),
        "published_version_label": (
            f"v{published.version_number} publicada" if published else "Sin versión publicada"
        ),
        "published_version_number": published.version_number if published else None,
        "published_at": published.published_at if published else None,
        "has_published_version": published is not None,
    }


def get_checklist(project: Project, membership=None) -> list[ChecklistItem]:
    a_wiz = profile_a_wizard_service.get_wizard_context(project, membership)
    b_wiz = profile_b_wizard_service.get_wizard_context(project, membership)
    rules_wiz = match_rules_wizard_service.get_rules_context(project, membership)

    source_a = source_persistence_service.get_source_dict(project)
    source_b = profile_b_persistence_service.get_source_b_dict(project)

    a_ready = (
        a_wiz.steps_complete >= a_wiz.steps_total
        and bool(source_a.get("fields"))
        and bool((source_a.get("file_type_code") or "").strip())
        and reject_a_type(source_a.get("file_type_code")) is None
    )
    b_ready = (
        b_wiz.steps_complete >= b_wiz.steps_total
        and bool(source_b.get("fields"))
        and bool((source_b.get("file_type_code") or "").strip())
        and reject_b_type(source_b.get("file_type_code")) is None
    )
    rules = match_rules_persistence_service.get_rules_dict(project)
    rules_errors, _ = match_rules_persistence_service.validate_rules_dict(
        project, rules, strict=True
    )
    rules_ready = not rules_errors and bool(rules.get("key"))

    return [
        ChecklistItem(
            "profile_a",
            "Perfil A",
            a_ready,
            (
                f"{a_wiz.file_type_label} · {a_wiz.fields_count} campos · 6/6"
                if a_ready
                else f"{a_wiz.steps_complete}/{a_wiz.steps_total} pasos"
            ),
            "file_match:profile_a_hub",
        ),
        ChecklistItem(
            "profile_b",
            "Perfil B",
            b_ready,
            (
                f"{b_wiz.file_type_label} · {b_wiz.fields_count} campos · 6/6"
                if b_ready
                else f"{b_wiz.steps_complete}/{b_wiz.steps_total} pasos"
            ),
            "file_match:profile_b_hub",
        ),
        ChecklistItem(
            "rules",
            "Reglas de cruce",
            rules_ready,
            (
                f"{rules_wiz.key_count} clave(s) · {rules_wiz.compare_count} compare"
                if rules_ready
                else "Falta clave usable o hay errores"
            ),
            "file_match:rules_hub",
        ),
    ]


def get_hub_context(user, project: Project, membership=None) -> PublishHubContext:
    publish = get_publish_context(project)
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


def _validate_side_strict(source: dict, *, side_label: str, reject_fn) -> OperationResult | None:
    if not (source.get("file_type_code") or "").strip():
        return OperationResult.failure(
            "validation_form",
            f"Complete el perfil {side_label} antes de publicar.",
            errors={"file_type_code": [f"Seleccione el tipo del archivo {side_label}."]},
        )
    wl = reject_fn(source.get("file_type_code"))
    if wl is not None:
        return wl

    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list,
    )

    normalized = copy.deepcopy(source)
    normalized["fields"] = normalize_fields_list(
        normalized.get("fields") or [],
        normalized.get("file_type_code") or "",
    )
    errors, warnings = source_persistence_service.validate_source_dict(
        normalized, strict=True
    )
    if errors:
        return OperationResult.failure(
            "validation_form",
            f"Complete y corrija el perfil {side_label} antes de publicar.",
            errors=errors,
            warnings=warnings,
        )
    return None


@transaction.atomic
def publish_match_definition(user, project: Project) -> OperationResult:
    if project.project_kind != Project.KIND_FILE_MATCH:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE MATCH.",
        )

    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para publicar la definición de este proyecto.",
        )

    draft = (
        DmsMappingVersion.objects.select_for_update()
        .filter(
            project=project,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        .select_related("source_profile")
        .order_by("-version_number")
        .first()
    )
    if draft is None:
        return OperationResult.failure(
            "not_found",
            "No hay borrador disponible para publicar.",
        )

    try:
        profile_a = draft.source_profile
    except DmsSourceProfile.DoesNotExist:
        return OperationResult.failure(
            "validation_form",
            "El borrador no tiene perfil A.",
        )

    try:
        profile_b = draft.match_source_b
    except FileMatchSourceB.DoesNotExist:
        return OperationResult.failure(
            "validation_form",
            "Complete el perfil B antes de publicar.",
        )

    try:
        rules_obj = draft.match_rules
    except FileMatchRules.DoesNotExist:
        return OperationResult.failure(
            "validation_form",
            "Complete las reglas de cruce antes de publicar.",
        )

    source_a = source_persistence_service.profile_to_dict(profile_a)
    source_b = profile_b_persistence_service.profile_to_dict(profile_b)
    rules = match_rules_persistence_service.normalize_rules_dict(rules_obj.rules or {})

    a_err = _validate_side_strict(source_a, side_label="A", reject_fn=reject_a_type)
    if a_err is not None:
        return a_err
    b_err = _validate_side_strict(source_b, side_label="B", reject_fn=reject_b_type)
    if b_err is not None:
        return b_err

    rules_errors, rules_warnings = match_rules_persistence_service.validate_rules_dict(
        project, rules, strict=True
    )
    if rules_errors:
        return OperationResult.failure(
            "validation_form",
            "Complete y corrija las reglas de cruce antes de publicar.",
            errors=rules_errors,
            warnings=rules_warnings,
        )

    # Persist normalized snapshots on draft before freeze
    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list,
    )

    source_a["fields"] = normalize_fields_list(
        source_a.get("fields") or [], source_a.get("file_type_code") or ""
    )
    source_b["fields"] = normalize_fields_list(
        source_b.get("fields") or [], source_b.get("file_type_code") or ""
    )
    cfg_a = dict(source_a.get("config") or {})
    cfg_a["match_side"] = "A"
    source_a["config"] = cfg_a
    cfg_b = dict(source_b.get("config") or {})
    cfg_b["match_side"] = "B"
    source_b["config"] = cfg_b

    source_persistence_service.apply_dict_to_profile(profile_a, source_a)
    profile_a.save()
    profile_b_persistence_service.apply_dict_to_profile(profile_b, source_b)
    profile_b.save()
    rules_obj.rules = rules
    rules_obj.save(update_fields=["rules", "updated_at"])

    warnings = rules_warnings or {}

    try:
        now = timezone.now()
        draft.status = DmsMappingVersion.STATUS_PUBLISHED
        draft.published_at = now
        draft.published_by = user
        draft.save(update_fields=["status", "published_at", "published_by", "updated_at"])

        config, _created = DmsProjectConfig.objects.select_for_update().get_or_create(
            project=project,
        )
        config.current_version = draft
        config.save(update_fields=["current_version", "updated_at"])

        next_number = draft.version_number + 1
        new_draft = DmsMappingVersion.objects.create(
            project=project,
            version_number=next_number,
            status=DmsMappingVersion.STATUS_DRAFT,
        )

        DmsSourceProfile.objects.create(
            version=new_draft,
            **source_persistence_service.profile_defaults_from_dict(source_a),
        )
        FileMatchSourceB.objects.create(
            version=new_draft,
            **source_persistence_service.profile_defaults_from_dict(source_b),
        )
        FileMatchRules.objects.create(
            version=new_draft,
            rules=copy.deepcopy(rules),
        )

        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("publish_match_definition unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al publicar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message=(
            f"Definición v{draft.version_number} publicada correctamente. "
            f"Nuevo borrador v{next_number} listo para edición."
        ),
        payload={
            "published_version": draft,
            "new_draft_version": new_draft,
            "published_version_number": draft.version_number,
            "new_draft_version_number": next_number,
            "warnings": warnings,
            "warning_messages": source_persistence_service.flatten_validation_messages(
                warnings
            ),
        },
    )
