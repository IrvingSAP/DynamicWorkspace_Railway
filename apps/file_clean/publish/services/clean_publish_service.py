"""Publicar versión File Clean (perfil + clean_rules)."""

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
from apps.file_clean.profile.services import profile_wizard_service
from apps.file_clean.rules.services import clean_rules_persistence_service as rules_svc
from apps.file_clean.rules.services import clean_rules_validation_service as validation
from apps.projects.models import Project

logger = logging.getLogger(__name__)

MSG_KIND = "Este proyecto no es de tipo File Clean."
MSG_FORBIDDEN = "No tiene permiso para publicar la versión de este proyecto."
MSG_NO_DRAFT = "No hay borrador disponible para publicar."
MSG_NO_PROFILE = "El borrador no tiene perfil de lectura."
MSG_PROFILE = "Complete y corrija el perfil de lectura antes de publicar."
MSG_NO_FIELDS = "Complete el perfil de lectura con al menos un campo antes de publicar."
MSG_NO_RULES = "Habilite al menos una regla de limpieza antes de publicar."
MSG_RULES = "Corrija las reglas habilitadas antes de publicar."
MSG_UNEXPECTED = "Ocurrió un error al publicar. Si persiste, contacte al administrador."
MSG_STEPS_INCOMPLETE = (
    "Complete los pasos anteriores (Perfil y Reglas) antes de publicar."
)
MSG_STEP_PROFILE = "Complete el paso Perfil antes de publicar."
MSG_STEP_RULES = "Complete el paso Reglas antes de publicar."


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
    publish_blocked_reason: str = ""
    summary: dict = field(default_factory=dict)
    rule_issues: list[dict] = field(default_factory=list)
    version_history: list[dict] = field(default_factory=list)


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


def list_version_history(project: Project, *, limit: int = 20) -> list[dict]:
    versions = (
        DmsMappingVersion.objects.filter(project=project)
        .order_by("-version_number")[:limit]
    )
    rows = []
    for version in versions:
        rows.append(
            {
                "version_number": version.version_number,
                "status": version.status,
                "status_label": (
                    "Publicada"
                    if version.status == DmsMappingVersion.STATUS_PUBLISHED
                    else "Borrador"
                    if version.status == DmsMappingVersion.STATUS_DRAFT
                    else version.status
                ),
                "published_at": version.published_at,
                "published_by": (
                    version.published_by.username if version.published_by_id else None
                ),
            }
        )
    return rows


def _collect_enabled_rule_issues(source: dict) -> list[dict]:
    field_names = validation.profile_field_names(source)
    raw_rules = (source.get("config") or {}).get(rules_svc.CONFIG_KEY) or []
    if not isinstance(raw_rules, list):
        raw_rules = []
    issues = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("enabled", True)):
            continue
        rule = validation.sanitize_rule(item, field_names=field_names)
        errors = validation.validate_rule(rule, field_names=field_names)
        field_errors = {k: v for k, v in errors.items() if k != "_codes"}
        if not field_errors:
            continue
        messages = []
        for msgs in field_errors.values():
            messages.extend(msgs)
        issues.append(
            {
                "id": rule.get("id"),
                "code": rule.get("code"),
                "field_name": rule.get("field_name"),
                "messages": messages,
                "error_code": validation.primary_error_code(errors),
            }
        )
    return issues


def validate_for_publish(project: Project) -> OperationResult | None:
    """Return failure OperationResult if P1–P5 fail; None if OK."""
    source = source_persistence_service.get_source_dict(project)

    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list,
    )

    normalized = copy.deepcopy(source)
    normalized["fields"] = normalize_fields_list(
        normalized.get("fields") or [],
        normalized.get("file_type_code") or "",
    )

    if not (normalized.get("file_type_code") or "").strip():
        return OperationResult.failure(
            "validation_form",
            MSG_PROFILE,
            errors={"file_type_code": ["Seleccione el tipo de archivo."]},
        )

    if not normalized.get("fields"):
        return OperationResult.failure(
            "validation_form",
            MSG_NO_FIELDS,
            errors={"fields": ["Defina al menos un campo en el perfil."]},
        )

    errors, warnings = source_persistence_service.validate_source_dict(
        normalized, strict=True
    )
    if errors:
        return OperationResult.failure(
            "validation_form",
            MSG_PROFILE,
            errors=errors,
            warnings=warnings,
        )

    rules = rules_svc.get_rules(project)
    enabled = [r for r in rules if r.get("enabled")]
    if not enabled:
        return OperationResult.failure(
            "validation_form",
            MSG_NO_RULES,
            errors={"rules": [MSG_NO_RULES]},
        )

    issues = _collect_enabled_rule_issues(normalized)
    if issues:
        detail_errors: dict[str, list[str]] = {}
        for issue in issues:
            key = f"rule:{issue.get('code')}:{issue.get('field_name') or 'global'}"
            detail_errors[key] = issue["messages"]
        return OperationResult.failure(
            "validation_form",
            MSG_RULES,
            errors=detail_errors,
            rule_issues=issues,
        )
    return None


def get_checklist(project: Project, membership=None) -> list[ChecklistItem]:
    wizard = profile_wizard_service.get_wizard_context(project, membership)
    source = source_persistence_service.get_source_dict(project)
    rules_ctx = rules_svc.get_hub_context(project)
    issues = _collect_enabled_rule_issues(source)

    profile_ready = (
        wizard.steps_complete >= wizard.steps_total
        and bool(source.get("fields"))
        and bool((source.get("file_type_code") or "").strip())
    )
    rules_ready = rules_ctx["rules_enabled_count"] > 0 and not issues

    return [
        ChecklistItem(
            "profile",
            "Perfil de lectura",
            profile_ready,
            (
                f"{wizard.file_type_label} · {wizard.fields_count} campos · "
                f"{wizard.steps_complete}/{wizard.steps_total}"
                if profile_ready
                else f"{wizard.steps_complete}/{wizard.steps_total} pasos"
            ),
            "file_clean:profile_hub",
        ),
        ChecklistItem(
            "rules",
            "Reglas de limpieza",
            rules_ready,
            (
                f"{rules_ctx['rules_enabled_count']} habilitadas · {rules_ctx['rules_count']} total"
                if rules_ctx["rules_enabled_count"] and not issues
                else (
                    f"{len(issues)} regla(s) inválida(s)"
                    if issues
                    else "Falta al menos una regla habilitada"
                )
            ),
            "file_clean:rules_hub",
        ),
    ]


def _publish_blocked_reason(checklist: list[ChecklistItem]) -> str:
    missing = {item.code for item in checklist if not item.ready}
    if not missing:
        return ""
    needs_profile = "profile" in missing
    needs_rules = "rules" in missing
    if needs_profile and needs_rules:
        return MSG_STEPS_INCOMPLETE
    if needs_profile:
        return MSG_STEP_PROFILE
    if needs_rules:
        return MSG_STEP_RULES
    return MSG_STEPS_INCOMPLETE


def get_hub_context(user, project: Project, membership=None) -> PublishHubContext:
    publish = get_publish_context(project)
    checklist = get_checklist(project, membership)
    can_edit = source_persistence_service.user_can_edit_source(user, project)
    blocking = [item.label for item in checklist if not item.ready]
    source = source_persistence_service.get_source_dict(project)
    rules_ctx = rules_svc.get_hub_context(project)
    wizard = profile_wizard_service.get_wizard_context(project, membership)
    issues = _collect_enabled_rule_issues(source)
    publish_fail = validate_for_publish(project)
    can_publish = can_edit and not blocking and publish_fail is None
    blocked_reason = _publish_blocked_reason(checklist)
    if not can_publish and not blocked_reason:
        blocked_reason = (
            publish_fail.user_message if publish_fail is not None else MSG_STEPS_INCOMPLETE
        )

    encoding = source.get("encoding_code") or "—"
    file_type = wizard.file_type_label
    summary = {
        "file_type_label": file_type,
        "encoding": encoding,
        "fields_count": wizard.fields_count,
        "rules_enabled_count": rules_ctx["rules_enabled_count"],
        "rules_count": rules_ctx["rules_count"],
        "rules_disabled_count": max(
            0, rules_ctx["rules_count"] - rules_ctx["rules_enabled_count"]
        ),
    }

    return PublishHubContext(
        draft_version_number=publish["draft_version_number"],
        published_version_label=publish["published_version_label"],
        published_version_number=publish["published_version_number"],
        has_published_version=publish["has_published_version"],
        can_publish=can_publish,
        checklist=checklist,
        blocking_reasons=blocking,
        publish_blocked_reason=blocked_reason,
        summary=summary,
        rule_issues=issues,
        version_history=list_version_history(project),
    )


@transaction.atomic
def publish_clean_definition(user, project: Project) -> OperationResult:
    if project.project_kind != Project.KIND_FILE_CLEAN:
        return OperationResult.failure("forbidden", MSG_KIND)

    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure("forbidden", MSG_FORBIDDEN)

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
        return OperationResult.failure("not_found", MSG_NO_DRAFT)

    try:
        profile = draft.source_profile
    except DmsSourceProfile.DoesNotExist:
        return OperationResult.failure("validation_form", MSG_NO_PROFILE)

    precheck = validate_for_publish(project)
    if precheck is not None:
        return precheck

    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list,
    )

    source = source_persistence_service.profile_to_dict(profile)
    source["fields"] = normalize_fields_list(
        source.get("fields") or [],
        source.get("file_type_code") or "",
    )

    # Normalize enabled rule params before freeze
    field_names = validation.profile_field_names(source)
    raw_rules = (source.get("config") or {}).get(rules_svc.CONFIG_KEY) or []
    normalized_rules = []
    if isinstance(raw_rules, list):
        for index, item in enumerate(raw_rules):
            if not isinstance(item, dict):
                continue
            rule = validation.sanitize_rule(item, field_names=field_names)
            if not rule.get("id"):
                import uuid

                rule["id"] = str(uuid.uuid4())
            rule["sort_order"] = index
            normalized_rules.append(rule)
    config = dict(source.get("config") or {})
    config[rules_svc.CONFIG_KEY] = normalized_rules
    source["config"] = config
    source_persistence_service.apply_dict_to_profile(profile, source)
    profile.save()

    try:
        now = timezone.now()
        draft.status = DmsMappingVersion.STATUS_PUBLISHED
        draft.published_at = now
        draft.published_by = user
        draft.save(update_fields=["status", "published_at", "published_by", "updated_at"])

        dms_config, _created = DmsProjectConfig.objects.select_for_update().get_or_create(
            project=project,
        )
        dms_config.current_version = draft
        dms_config.save(update_fields=["current_version", "updated_at"])

        next_number = draft.version_number + 1
        new_draft = DmsMappingVersion.objects.create(
            project=project,
            version_number=next_number,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        DmsSourceProfile.objects.create(
            version=new_draft,
            **source_persistence_service.profile_defaults_from_dict(source),
        )
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("publish_clean_definition unexpected project=%s", project.slug)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(
        user_message=(
            f"Versión v{draft.version_number} publicada correctamente. "
            f"Nuevo borrador v{next_number} listo para edición."
        ),
        payload={
            "published_version": draft,
            "new_draft_version": new_draft,
            "published_version_number": draft.version_number,
            "new_draft_version_number": next_number,
            "warnings": {},
            "warning_messages": [],
        },
    )
