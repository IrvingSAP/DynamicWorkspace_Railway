"""Persistencia de clean_rules en DmsSourceProfile.config (sin migración)."""

from __future__ import annotations

import copy
import logging
import uuid

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.file_clean.rules.services import clean_rules_catalog as catalog
from apps.file_clean.rules.services import clean_rules_validation_service as validation
from apps.projects.models import Project

logger = logging.getLogger(__name__)

CONFIG_KEY = "clean_rules"

MSG_SAVED = "Reglas de limpieza guardadas correctamente."
MSG_ADDED = "Regla añadida correctamente."
MSG_UPDATED = "Regla actualizada correctamente."
MSG_DELETED = "Regla eliminada."
MSG_TOGGLED = "Estado de la regla actualizado."
MSG_REORDERED = "Orden de reglas guardado."
MSG_FORBIDDEN = "No tiene permiso para editar las reglas de este proyecto."
MSG_NOT_FOUND = "Regla no encontrada."
MSG_KIND = "Este proyecto no es de tipo File Clean."


def _ensure_kind(project: Project) -> OperationResult | None:
    if project.project_kind != Project.KIND_FILE_CLEAN:
        return OperationResult.failure("forbidden", MSG_KIND)
    return None


def _ensure_edit(user, project: Project) -> OperationResult | None:
    kind_err = _ensure_kind(project)
    if kind_err:
        return kind_err
    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure("forbidden", MSG_FORBIDDEN)
    return None


def get_rules(project: Project) -> list[dict]:
    source = source_persistence_service.get_source_dict(project)
    raw = (source.get("config") or {}).get(CONFIG_KEY) or []
    if not isinstance(raw, list):
        return []
    rules = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        rule = {
            "id": str(item.get("id") or uuid.uuid4()),
            "code": (item.get("code") or "").strip(),
            "field_name": (item.get("field_name") or None),
            "params": item.get("params") or {},
            "enabled": bool(item.get("enabled", True)),
            "sort_order": int(item.get("sort_order") if item.get("sort_order") is not None else index),
        }
        rules.append(rule)
    rules.sort(key=lambda r: r["sort_order"])
    for index, rule in enumerate(rules):
        rule["sort_order"] = index
    return rules


def _write_rules(project: Project, rules: list[dict]) -> None:
    version = source_persistence_service.get_or_create_draft_version(project)
    profile = version.source_profile
    current = source_persistence_service.profile_to_dict(profile)
    config = dict(current.get("config") or {})
    normalized = []
    for index, rule in enumerate(rules):
        item = copy.deepcopy(rule)
        if not item.get("id"):
            item["id"] = str(uuid.uuid4())
        item["sort_order"] = index
        item["enabled"] = bool(item.get("enabled", True))
        normalized.append(item)
    config[CONFIG_KEY] = normalized
    current["config"] = config
    source_persistence_service.apply_dict_to_profile(profile, current)
    profile.save()
    version.save(update_fields=["updated_at"])
    project.save(update_fields=["updated_at"])


def get_hub_context(project: Project) -> dict:
    source = source_persistence_service.get_source_dict(project)
    field_names = sorted(validation.profile_field_names(source))
    rules = get_rules(project)
    rows = []
    for rule in rules:
        code = rule["code"]
        scope = catalog.scope_for(code) if code in catalog.ALLOWED_CODES else catalog.SCOPE_FIELD
        rows.append(
            {
                **rule,
                "scope": scope,
                "scope_label": catalog.scope_label(scope),
                "label": (catalog.RULE_CATALOG.get(code) or {}).get("label") or code,
                "params_summary": catalog.params_summary(code, rule.get("params")),
            }
        )
    enabled_count = sum(1 for r in rows if r["enabled"])
    return {
        "rules": rows,
        "rules_count": len(rows),
        "rules_enabled_count": enabled_count,
        "field_names": field_names,
        "catalog_choices": catalog.catalog_choices(),
        "source": source,
        "has_profile_fields": bool(field_names),
    }


def save_all_rules(user, project: Project, rules: list[dict]) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    source = source_persistence_service.get_source_dict(project)
    field_names = validation.profile_field_names(source)
    cleaned = []
    for index, raw in enumerate(rules):
        rule = validation.sanitize_rule(raw, field_names=field_names)
        rule["sort_order"] = index
        if not rule["id"]:
            rule["id"] = str(uuid.uuid4())
        errors = validation.validate_rule(rule, field_names=field_names)
        # drop _codes from field errors for OperationResult
        field_errors = {k: v for k, v in errors.items() if k != "_codes"}
        if field_errors:
            return OperationResult.failure(
                validation.primary_error_code(errors),
                validation.user_message_for_errors(errors),
                errors=field_errors,
            )
        cleaned.append(rule)
    try:
        _write_rules(project, cleaned)
    except Exception:
        logger.exception("save_all_clean_rules unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_SAVED, payload={"rules": cleaned})


def add_rule(user, project: Project, data: dict) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    source = source_persistence_service.get_source_dict(project)
    field_names = validation.profile_field_names(source)
    rule = validation.sanitize_rule(
        {
            "id": str(uuid.uuid4()),
            "code": data.get("code"),
            "field_name": data.get("field_name"),
            "params": data.get("params") or {},
            "enabled": data.get("enabled", True),
            "sort_order": 0,
        },
        field_names=field_names,
    )
    errors = validation.validate_rule(rule, field_names=field_names)
    field_errors = {k: v for k, v in errors.items() if k != "_codes"}
    if field_errors:
        return OperationResult.failure(
            validation.primary_error_code(errors),
            validation.user_message_for_errors(errors),
            errors=field_errors,
        )
    rules = get_rules(project)
    rules.append(rule)
    try:
        _write_rules(project, rules)
    except Exception:
        logger.exception("add_clean_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_ADDED, payload={"rule": rule})


def update_rule(user, project: Project, rule_id: str, data: dict) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    rules = get_rules(project)
    index = next((i for i, r in enumerate(rules) if r["id"] == rule_id), None)
    if index is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    source = source_persistence_service.get_source_dict(project)
    field_names = validation.profile_field_names(source)
    rule = validation.sanitize_rule(
        {
            "id": rule_id,
            "code": data.get("code", rules[index]["code"]),
            "field_name": data.get("field_name", rules[index].get("field_name")),
            "params": data.get("params", rules[index].get("params")),
            "enabled": data.get("enabled", rules[index].get("enabled", True)),
            "sort_order": rules[index]["sort_order"],
        },
        field_names=field_names,
    )
    errors = validation.validate_rule(rule, field_names=field_names)
    field_errors = {k: v for k, v in errors.items() if k != "_codes"}
    if field_errors:
        return OperationResult.failure(
            validation.primary_error_code(errors),
            validation.user_message_for_errors(errors),
            errors=field_errors,
        )
    rules[index] = rule
    try:
        _write_rules(project, rules)
    except Exception:
        logger.exception("update_clean_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_UPDATED, payload={"rule": rule})


def delete_rule(user, project: Project, rule_id: str) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    rules = get_rules(project)
    new_rules = [r for r in rules if r["id"] != rule_id]
    if len(new_rules) == len(rules):
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    try:
        _write_rules(project, new_rules)
    except Exception:
        logger.exception("delete_clean_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_DELETED)


def toggle_rule(user, project: Project, rule_id: str) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    rules = get_rules(project)
    found = False
    for rule in rules:
        if rule["id"] == rule_id:
            rule["enabled"] = not bool(rule.get("enabled", True))
            found = True
            break
    if not found:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    try:
        _write_rules(project, rules)
    except Exception:
        logger.exception("toggle_clean_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_TOGGLED)


def move_rule(user, project: Project, rule_id: str, direction: str) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    rules = get_rules(project)
    index = next((i for i, r in enumerate(rules) if r["id"] == rule_id), None)
    if index is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    if direction == "up" and index > 0:
        rules[index - 1], rules[index] = rules[index], rules[index - 1]
    elif direction == "down" and index < len(rules) - 1:
        rules[index + 1], rules[index] = rules[index], rules[index + 1]
    else:
        return OperationResult.success(user_message=MSG_REORDERED, payload={"rules": rules})
    try:
        _write_rules(project, rules)
    except Exception:
        logger.exception("move_clean_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_REORDERED, payload={"rules": rules})


def orphaned_field_refs(project: Project) -> list[str]:
    """Rule ids (or codes) that reference missing profile fields."""
    source = source_persistence_service.get_source_dict(project)
    field_names = validation.profile_field_names(source)
    orphans = []
    for rule in get_rules(project):
        code = rule["code"]
        if catalog.scope_for(code) != catalog.SCOPE_FIELD:
            continue
        name = rule.get("field_name")
        if name and name not in field_names:
            orphans.append(rule["id"])
    return orphans
