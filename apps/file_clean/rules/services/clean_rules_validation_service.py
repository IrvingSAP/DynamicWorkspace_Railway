"""Validación de reglas File Clean (guardar / P5)."""

from __future__ import annotations

import re

from apps.file_clean.rules.services import clean_rules_catalog as catalog

COMPOSE_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
COMPOSE_FIELD_RE = re.compile(r"^field:([A-Za-z_][A-Za-z0-9_]*)$")

MSG_BY_CODE = {
    "file_clean_rule_unknown": "Código de regla no permitido en File Clean.",
    "file_clean_rule_field_missing": "Indique un campo del perfil válido para esta regla.",
    "file_clean_replace_map_invalid": "El mapa de reemplazo debe ser un objeto no vacío.",
    "file_clean_replace_find_required": "Indique el texto a buscar (find) en replace.",
    "file_clean_replace_regex_unsupported": "Regex en replace no está disponible en File Clean MVP.",
    "file_clean_compose_invalid": "Plantilla compose inválida o con tokens no permitidos.",
    "file_clean_dedupe_key_required": "Indique al menos un campo clave para dedupe_rows.",
    "validation_form": "Revise los datos marcados; no se pudo guardar.",
}


def profile_field_names(source: dict) -> set[str]:
    names: set[str] = set()
    for item in source.get("fields") or []:
        name = (item.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def _fail(errors: dict, field: str, code: str, message: str | None = None) -> None:
    errors.setdefault(field, []).append(message or MSG_BY_CODE.get(code, code))
    errors.setdefault("_codes", []).append(code)


def _parse_bool(value, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "si", "sí"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _parse_replace_map(raw) -> dict | None:
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}
    if isinstance(raw, str):
        mapping: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if "→" in line:
                left, right = line.split("→", 1)
            elif "->" in line:
                left, right = line.split("->", 1)
            elif "=" in line:
                left, right = line.split("=", 1)
            else:
                return None
            mapping[left.strip()] = right.strip()
        return mapping
    return None


def normalize_params(code: str, params: dict | None) -> dict:
    params = dict(params or {})
    if code == "null_tokens":
        tokens = params.get("tokens")
        if isinstance(tokens, str):
            tokens = [part.strip() for part in tokens.split(",")]
        if not isinstance(tokens, list) or not tokens:
            tokens = ["N/A", "null", "—", ""]
        return {"tokens": [str(t) for t in tokens]}
    if code == "date_normalize":
        formats = params.get("input_formats") or []
        if isinstance(formats, str):
            formats = [f.strip() for f in formats.split(",") if f.strip()]
        out = (params.get("output_format") or "%Y-%m-%d").strip()
        return {"input_formats": list(formats), "output_format": out}
    if code == "number_normalize":
        return {
            "decimal_sep": (params.get("decimal_sep") or ".").strip() or ".",
            "thousands_sep": (params.get("thousands_sep") or ",").strip(),
        }
    if code == "replace_map":
        mapping = _parse_replace_map(params.get("map"))
        return {
            "map": mapping or {},
            "case_insensitive": _parse_bool(params.get("case_insensitive"), False),
        }
    if code == "replace":
        return {
            "find": "" if params.get("find") is None else str(params.get("find")),
            "replace": "" if params.get("replace") is None else str(params.get("replace")),
            "all": _parse_bool(params.get("all"), True),
            "ignore_case": _parse_bool(params.get("ignore_case"), False),
            "regex": _parse_bool(params.get("regex"), False),
        }
    if code == "compose":
        result = {
            "template": "" if params.get("template") is None else str(params.get("template")),
            "seq_pad_char": str(params.get("seq_pad_char") or "0")[:1] or "0",
        }
        try:
            result["seq_start"] = int(params.get("seq_start") or 1)
        except (TypeError, ValueError):
            result["seq_start"] = 1
        try:
            result["seq_step"] = int(params.get("seq_step") or 1)
        except (TypeError, ValueError):
            result["seq_step"] = 1
        width = params.get("seq_width")
        if width not in (None, ""):
            try:
                result["seq_width"] = int(width)
            except (TypeError, ValueError):
                pass
        return result
    if code == "dedupe_rows":
        keys = params.get("key_fields") or []
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split(",") if k.strip()]
        return {"key_fields": list(keys)}
    if code == "encoding_normalize":
        return {
            "target_encoding": (params.get("target_encoding") or "utf-8").strip() or "utf-8",
            "strip_bom": _parse_bool(params.get("strip_bom"), True),
        }
    return {}


def validate_rule(
    rule: dict,
    *,
    field_names: set[str],
    require_enabled_valid: bool = True,
) -> dict[str, list[str]]:
    """Returns errors dict (empty if ok). Includes special key _codes."""
    errors: dict[str, list[str]] = {}
    code = (rule.get("code") or "").strip()
    if code not in catalog.ALLOWED_CODES:
        _fail(errors, "code", "file_clean_rule_unknown")
        return errors

    scope = catalog.scope_for(code)
    field_name = (rule.get("field_name") or "").strip() or None
    if scope == catalog.SCOPE_FIELD:
        if not field_name or field_name not in field_names:
            _fail(errors, "field_name", "file_clean_rule_field_missing")
    else:
        field_name = None

    enabled = bool(rule.get("enabled", True))
    if not enabled and not require_enabled_valid:
        # Still validate structure lightly when disabled? Spec: disabled don't block publish,
        # but saving should still validate params if provided.
        pass

    params = normalize_params(code, rule.get("params"))

    if code == "replace_map":
        mapping = params.get("map")
        if not isinstance(mapping, dict) or len(mapping) == 0:
            _fail(errors, "params", "file_clean_replace_map_invalid")
    elif code == "replace":
        if params.get("regex"):
            _fail(errors, "params", "file_clean_replace_regex_unsupported")
        if not params.get("find"):
            _fail(errors, "params", "file_clean_replace_find_required")
    elif code == "compose":
        template = params.get("template") or ""
        if not template.strip():
            _fail(errors, "params", "file_clean_compose_invalid", "Indique la plantilla compose.")
        else:
            for raw_token in COMPOSE_TOKEN_RE.findall(template):
                token = raw_token.strip()
                if token == "value" or token == "seq":
                    continue
                m = COMPOSE_FIELD_RE.match(token)
                if m:
                    ref = m.group(1)
                    if ref not in field_names:
                        _fail(
                            errors,
                            "params",
                            "file_clean_compose_invalid",
                            f"El token {{field:{ref}}} no existe en el perfil.",
                        )
                    continue
                _fail(
                    errors,
                    "params",
                    "file_clean_compose_invalid",
                    f"Token {{{token}}} no permitido. Use {{value}}, {{field:nombre}} o {{seq}}.",
                )
    elif code == "dedupe_rows":
        keys = params.get("key_fields") or []
        if not keys:
            _fail(errors, "params", "file_clean_dedupe_key_required")
        else:
            for key in keys:
                if key not in field_names:
                    _fail(
                        errors,
                        "params",
                        "file_clean_rule_field_missing",
                        f"Campo clave «{key}» no existe en el perfil.",
                    )

    # strip internal marker for callers that only want field errors
    return errors


def primary_error_code(errors: dict) -> str:
    codes = errors.get("_codes") or []
    if codes:
        return codes[0]
    return "validation_form"


def user_message_for_errors(errors: dict) -> str:
    code = primary_error_code(errors)
    return MSG_BY_CODE.get(code, MSG_BY_CODE["validation_form"])


def sanitize_rule(rule: dict, *, field_names: set[str]) -> dict:
    """Normalize a rule dict for persistence (does not validate)."""
    code = (rule.get("code") or "").strip()
    scope = catalog.scope_for(code) if code in catalog.ALLOWED_CODES else catalog.SCOPE_FIELD
    field_name = (rule.get("field_name") or "").strip() or None
    if scope != catalog.SCOPE_FIELD:
        field_name = None
    params = normalize_params(code, rule.get("params")) if code in catalog.ALLOWED_CODES else {}
    # strip regex key for replace if false
    if code == "replace":
        params.pop("regex", None)
    return {
        "id": str(rule.get("id") or "").strip(),
        "code": code,
        "field_name": field_name,
        "params": params,
        "enabled": bool(rule.get("enabled", True)),
        "sort_order": int(rule.get("sort_order") or 0),
    }
