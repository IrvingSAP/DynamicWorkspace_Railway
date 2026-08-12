"""Validación de reglas Split/Merge."""

from __future__ import annotations

from apps.file_split_merge.rules.services import split_merge_rules_catalog as catalog

MSG_BY_CODE = {
    "sm_rule_unknown": "Código de regla no permitido en File Split/Merge.",
    "sm_rule_operation_mismatch": "Esta regla no corresponde a la operación actual.",
    "sm_rule_field_missing": "Seleccione un campo del perfil de lectura.",
    "sm_rule_n_invalid": "Indique un número de filas mayor o igual a 1.",
    "sm_rule_bytes_invalid": "Indique un tamaño en bytes mayor o igual a 1.",
    "sm_rule_mode_invalid": "Seleccione error o fill_empty.",
    "sm_rule_dedupe_keys": "Indique al menos una clave de deduplicación válida.",
    "sm_rule_keep_invalid": "Seleccione first o last.",
    "sm_profile_incomplete": "Complete el perfil de lectura antes de definir reglas.",
    "sm_operation_required": "Seleccione Split o Merge.",
    "validation_form": "Revise los parámetros de la regla.",
}


def profile_field_names(source: dict) -> set[str]:
    names: set[str] = set()
    for item in source.get("fields") or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def profile_is_complete(source: dict) -> bool:
    if not (source.get("file_type_code") or "").strip():
        return False
    if not (source.get("capture_start") or {}).get("mode"):
        return False
    if not (source.get("capture_end") or {}).get("mode"):
        return False
    return bool(source.get("fields"))


def normalize_params(code: str, params: dict | None) -> dict:
    params = dict(params or {})
    if code == "max_rows":
        try:
            n = int(params.get("n") or 0)
        except (TypeError, ValueError):
            n = 0
        return {"n": n}
    if code == "max_bytes":
        try:
            b = int(params.get("bytes") or 0)
        except (TypeError, ValueError):
            b = 0
        return {"bytes": b}
    if code == "split_by_column":
        return {
            "field_name": (params.get("field_name") or "").strip(),
            "include_empty": bool(params.get("include_empty")),
        }
    if code in ("keep_header", "include_header"):
        if "value" not in params:
            return {"value": True}
        return {"value": bool(params.get("value"))}
    if code == "append":
        return {}
    if code == "missing_columns":
        mode = (params.get("mode") or "error").strip()
        return {"mode": mode}
    if code == "dedupe_rows":
        keys = params.get("keys") or []
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split(",") if k.strip()]
        else:
            keys = [str(k).strip() for k in keys if str(k).strip()]
        keep = (params.get("keep") or "first").strip()
        return {"keys": keys, "keep": keep}
    return params


def sanitize_rule(rule: dict, *, field_names: set[str]) -> dict:
    code = (rule.get("code") or "").strip()
    return {
        "id": str(rule.get("id") or ""),
        "code": code,
        "params": normalize_params(code, rule.get("params")),
        "enabled": bool(rule.get("enabled", True)),
        "sort_order": int(rule.get("sort_order") or 0),
    }


def validate_rule(
    rule: dict,
    *,
    field_names: set[str],
    operation: str,
) -> dict:
    errors: dict[str, list[str]] = {}
    codes: list[str] = []
    code = (rule.get("code") or "").strip()
    params = rule.get("params") or {}

    if code not in catalog.ALLOWED_CODES:
        errors.setdefault("code", []).append(MSG_BY_CODE["sm_rule_unknown"])
        codes.append("sm_rule_unknown")
        errors["_codes"] = codes
        return errors

    expected_op = catalog.operation_for_code(code)
    if expected_op and operation and expected_op != operation:
        errors.setdefault("code", []).append(MSG_BY_CODE["sm_rule_operation_mismatch"])
        codes.append("sm_rule_operation_mismatch")

    if code == "max_rows":
        if int(params.get("n") or 0) < 1:
            errors.setdefault("params", []).append(MSG_BY_CODE["sm_rule_n_invalid"])
            codes.append("sm_rule_n_invalid")
    elif code == "max_bytes":
        if int(params.get("bytes") or 0) < 1:
            errors.setdefault("params", []).append(MSG_BY_CODE["sm_rule_bytes_invalid"])
            codes.append("sm_rule_bytes_invalid")
    elif code == "split_by_column":
        name = (params.get("field_name") or "").strip()
        if not name or name not in field_names:
            errors.setdefault("params", []).append(MSG_BY_CODE["sm_rule_field_missing"])
            codes.append("sm_rule_field_missing")
    elif code == "missing_columns":
        if (params.get("mode") or "") not in ("error", "fill_empty"):
            errors.setdefault("params", []).append(MSG_BY_CODE["sm_rule_mode_invalid"])
            codes.append("sm_rule_mode_invalid")
    elif code == "dedupe_rows":
        keys = params.get("keys") or []
        valid = [k for k in keys if k in field_names]
        if not valid:
            errors.setdefault("params", []).append(MSG_BY_CODE["sm_rule_dedupe_keys"])
            codes.append("sm_rule_dedupe_keys")
        if (params.get("keep") or "first") not in ("first", "last"):
            errors.setdefault("params", []).append(MSG_BY_CODE["sm_rule_keep_invalid"])
            codes.append("sm_rule_keep_invalid")

    if codes:
        errors["_codes"] = codes
    return errors


def primary_error_code(errors: dict) -> str:
    codes = errors.get("_codes") or []
    return codes[0] if codes else "validation_form"


def user_message_for_errors(errors: dict) -> str:
    code = primary_error_code(errors)
    return MSG_BY_CODE.get(code, MSG_BY_CODE["validation_form"])
