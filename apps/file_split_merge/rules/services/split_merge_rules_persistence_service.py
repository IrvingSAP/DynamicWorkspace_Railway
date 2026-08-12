"""Persistencia de sm_rules en DmsSourceProfile.config (sin migración)."""

from __future__ import annotations

import copy
import logging
import uuid

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.file_split_merge.rules.services import split_merge_rules_catalog as catalog
from apps.file_split_merge.rules.services import (
    split_merge_rules_validation_service as validation,
)
from apps.projects.models import Project

logger = logging.getLogger(__name__)

CONFIG_KEY = "sm_rules"

MSG_SAVED = "Reglas Split/Merge guardadas correctamente."
MSG_ADDED = "Regla añadida correctamente."
MSG_UPDATED = "Regla actualizada correctamente."
MSG_DELETED = "Regla eliminada."
MSG_TOGGLED = "Estado de la regla actualizado."
MSG_REORDERED = "Orden de reglas guardado."
MSG_OPERATION = "Operación actualizada. Revise el catálogo de reglas."
MSG_OPERATION_CLEARED = "Operación cambiada. Se eliminaron las reglas anteriores."
MSG_FORBIDDEN = "No tiene permiso para editar las reglas de este proyecto."
MSG_NOT_FOUND = "Regla no encontrada."
MSG_KIND = "Este proyecto no es de tipo File Split/Merge."
MSG_PROFILE = validation.MSG_BY_CODE["sm_profile_incomplete"]
MSG_NO_OPERATION = "Seleccione Split o Merge antes de añadir reglas."


def _ensure_kind(project: Project) -> OperationResult | None:
    if project.project_kind != Project.KIND_FILE_SPLIT_MERGE:
        return OperationResult.failure("forbidden", MSG_KIND)
    return None


def _ensure_edit(user, project: Project) -> OperationResult | None:
    kind_err = _ensure_kind(project)
    if kind_err:
        return kind_err
    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure("forbidden", MSG_FORBIDDEN)
    return None


def get_payload(project: Project) -> dict:
    source = source_persistence_service.get_source_dict(project)
    raw = (source.get("config") or {}).get(CONFIG_KEY) or {}
    if not isinstance(raw, dict):
        raw = {}
    operation = (raw.get("operation") or "").strip() or None
    rules_raw = raw.get("rules") or []
    if not isinstance(rules_raw, list):
        rules_raw = []
    rules = []
    for index, item in enumerate(rules_raw):
        if not isinstance(item, dict):
            continue
        rules.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "code": (item.get("code") or "").strip(),
                "params": item.get("params") or {},
                "enabled": bool(item.get("enabled", True)),
                "sort_order": int(
                    item.get("sort_order") if item.get("sort_order") is not None else index
                ),
            }
        )
    rules.sort(key=lambda r: r["sort_order"])
    for index, rule in enumerate(rules):
        rule["sort_order"] = index
    return {"operation": operation, "rules": rules}


def get_rules(project: Project) -> list[dict]:
    return get_payload(project)["rules"]


def get_operation(project: Project) -> str | None:
    return get_payload(project)["operation"]


def _write_payload(project: Project, operation: str | None, rules: list[dict]) -> None:
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
        item["params"] = item.get("params") or {}
        normalized.append(item)
    config[CONFIG_KEY] = {
        "operation": operation or "",
        "rules": normalized,
    }
    current["config"] = config
    source_persistence_service.apply_dict_to_profile(profile, current)
    profile.save()
    version.save(update_fields=["updated_at"])
    project.save(update_fields=["updated_at"])


def is_rules_complete(project: Project) -> bool:
    payload = get_payload(project)
    operation = payload["operation"]
    rules = payload["rules"]
    if operation not in catalog.OPERATIONS:
        return False
    enabled = [r for r in rules if r.get("enabled")]
    if operation == catalog.OPERATION_SPLIT:
        return any(r.get("code") in catalog.SPLIT_PARTITION_CODES for r in enabled)
    return any(r.get("code") == "missing_columns" for r in enabled)


def get_hub_context(project: Project) -> dict:
    source = source_persistence_service.get_source_dict(project)
    field_names = sorted(validation.profile_field_names(source))
    payload = get_payload(project)
    operation = payload["operation"]
    rules = payload["rules"]
    rows = []
    for rule in rules:
        code = rule["code"]
        meta = catalog.RULE_CATALOG.get(code) or {}
        rows.append(
            {
                **rule,
                "label": meta.get("label") or code,
                "params_summary": catalog.params_summary(code, rule.get("params")),
                "field_missing": _rule_field_missing(rule, field_names),
            }
        )
    enabled_count = sum(1 for r in rows if r["enabled"])
    profile_complete = validation.profile_is_complete(source)
    return {
        "operation": operation,
        "operation_label": catalog.OPERATION_LABELS.get(operation or "", "Sin operación"),
        "rules": rows,
        "rules_count": len(rows),
        "rules_enabled_count": enabled_count,
        "rules_complete": is_rules_complete(project),
        "field_names": field_names,
        "catalog_choices": catalog.catalog_choices(operation),
        "source": source,
        "has_profile_fields": bool(field_names),
        "profile_complete": profile_complete,
    }


def _rule_field_missing(rule: dict, field_names: set[str]) -> bool:
    code = rule.get("code")
    params = rule.get("params") or {}
    if code == "split_by_column":
        name = (params.get("field_name") or "").strip()
        return bool(name) and name not in field_names
    if code == "dedupe_rows":
        keys = params.get("keys") or []
        return any(k not in field_names for k in keys)
    return False


def set_operation(
    user,
    project: Project,
    operation: str,
    *,
    confirm_clear: bool = False,
) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    source = source_persistence_service.get_source_dict(project)
    if not validation.profile_is_complete(source):
        return OperationResult.failure("validation_form", MSG_PROFILE)

    operation = (operation or "").strip()
    if operation not in catalog.OPERATIONS:
        return OperationResult.failure(
            "validation_form",
            validation.MSG_BY_CODE["sm_operation_required"],
        )

    payload = get_payload(project)
    current_op = payload["operation"]
    rules = payload["rules"]
    cleared = False

    if current_op and current_op != operation and rules and not confirm_clear:
        return OperationResult.failure(
            "confirm_required",
            "Cambiar de operación eliminará las reglas actuales. Confirme para continuar.",
            errors={"operation": ["confirm_clear"]},
        )

    if current_op and current_op != operation:
        rules = []
        cleared = True

    if operation == catalog.OPERATION_MERGE:
        has_missing = any(r.get("code") == "missing_columns" for r in rules)
        if not has_missing:
            rules.append(
                {
                    "id": str(uuid.uuid4()),
                    "code": "missing_columns",
                    "params": {"mode": "error"},
                    "enabled": True,
                    "sort_order": 0,
                }
            )

    try:
        _write_payload(project, operation, rules)
    except Exception:
        logger.exception("set_sm_operation unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    msg = MSG_OPERATION_CLEARED if cleared else MSG_OPERATION
    return OperationResult.success(
        user_message=msg,
        payload={"operation": operation, "rules": rules, "cleared": cleared},
    )


def add_rule(user, project: Project, data: dict) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    source = source_persistence_service.get_source_dict(project)
    if not validation.profile_is_complete(source):
        return OperationResult.failure("validation_form", MSG_PROFILE)
    payload = get_payload(project)
    operation = payload["operation"]
    if operation not in catalog.OPERATIONS:
        return OperationResult.failure("validation_form", MSG_NO_OPERATION)

    field_names = validation.profile_field_names(source)
    rule = validation.sanitize_rule(
        {
            "id": str(uuid.uuid4()),
            "code": data.get("code"),
            "params": data.get("params") or {},
            "enabled": data.get("enabled", True),
            "sort_order": 0,
        },
        field_names=field_names,
    )
    errors = validation.validate_rule(rule, field_names=field_names, operation=operation)
    field_errors = {k: v for k, v in errors.items() if k != "_codes"}
    if field_errors:
        return OperationResult.failure(
            validation.primary_error_code(errors),
            validation.user_message_for_errors(errors),
            errors=field_errors,
        )
    rules = payload["rules"]
    rules.append(rule)
    try:
        _write_payload(project, operation, rules)
    except Exception:
        logger.exception("add_sm_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_ADDED, payload={"rule": rule})


def update_rule(user, project: Project, rule_id: str, data: dict) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    payload = get_payload(project)
    operation = payload["operation"]
    rules = payload["rules"]
    index = next((i for i, r in enumerate(rules) if r["id"] == rule_id), None)
    if index is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    source = source_persistence_service.get_source_dict(project)
    field_names = validation.profile_field_names(source)
    rule = validation.sanitize_rule(
        {
            "id": rule_id,
            "code": data.get("code", rules[index]["code"]),
            "params": data.get("params", rules[index].get("params")),
            "enabled": data.get("enabled", rules[index].get("enabled", True)),
            "sort_order": rules[index]["sort_order"],
        },
        field_names=field_names,
    )
    errors = validation.validate_rule(
        rule, field_names=field_names, operation=operation or ""
    )
    field_errors = {k: v for k, v in errors.items() if k != "_codes"}
    if field_errors:
        return OperationResult.failure(
            validation.primary_error_code(errors),
            validation.user_message_for_errors(errors),
            errors=field_errors,
        )
    rules[index] = rule
    try:
        _write_payload(project, operation, rules)
    except Exception:
        logger.exception("update_sm_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_UPDATED, payload={"rule": rule})


def delete_rule(user, project: Project, rule_id: str) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    payload = get_payload(project)
    rules = payload["rules"]
    new_rules = [r for r in rules if r["id"] != rule_id]
    if len(new_rules) == len(rules):
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    try:
        _write_payload(project, payload["operation"], new_rules)
    except Exception:
        logger.exception("delete_sm_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_DELETED)


def toggle_rule(user, project: Project, rule_id: str) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    payload = get_payload(project)
    rules = payload["rules"]
    found = False
    for rule in rules:
        if rule["id"] == rule_id:
            rule["enabled"] = not bool(rule.get("enabled", True))
            found = True
            break
    if not found:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    try:
        _write_payload(project, payload["operation"], rules)
    except Exception:
        logger.exception("toggle_sm_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_TOGGLED)


def move_rule(user, project: Project, rule_id: str, direction: str) -> OperationResult:
    err = _ensure_edit(user, project)
    if err:
        return err
    payload = get_payload(project)
    rules = payload["rules"]
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
        _write_payload(project, payload["operation"], rules)
    except Exception:
        logger.exception("move_sm_rule unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_REORDERED, payload={"rules": rules})
