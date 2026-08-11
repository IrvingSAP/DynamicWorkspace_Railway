"""Catálogo de reglas File Clean (subset de limpieza)."""

from __future__ import annotations

SCOPE_FIELD = "field"
SCOPE_GLOBAL = "global"
SCOPE_FILE = "file"

# code → metadata
RULE_CATALOG: dict[str, dict] = {
    "trim": {
        "label": "Quitar espacios extremos",
        "scope": SCOPE_FIELD,
        "priority": "P0",
        "params_schema": [],
    },
    "strip_invisible": {
        "label": "Caracteres no imprimibles / zero-width",
        "scope": SCOPE_FIELD,
        "priority": "P0",
        "params_schema": [],
    },
    "case_upper": {
        "label": "Mayúsculas",
        "scope": SCOPE_FIELD,
        "priority": "P0",
        "params_schema": [],
    },
    "case_lower": {
        "label": "Minúsculas",
        "scope": SCOPE_FIELD,
        "priority": "P0",
        "params_schema": [],
    },
    "null_tokens": {
        "label": "Tokens nulos → vacío",
        "scope": SCOPE_FIELD,
        "priority": "P0",
        "params_schema": ["tokens"],
    },
    "date_normalize": {
        "label": "Normalizar fechas",
        "scope": SCOPE_FIELD,
        "priority": "P1",
        "params_schema": ["input_formats", "output_format"],
    },
    "number_normalize": {
        "label": "Normalizar números",
        "scope": SCOPE_FIELD,
        "priority": "P1",
        "params_schema": ["decimal_sep", "thousands_sep"],
    },
    "replace_map": {
        "label": "Mapa valor completo (match exacto)",
        "scope": SCOPE_FIELD,
        "priority": "P1",
        "params_schema": ["map", "case_insensitive"],
    },
    "replace": {
        "label": "Find/replace dentro del string",
        "scope": SCOPE_FIELD,
        "priority": "P1",
        "params_schema": ["find", "replace", "all", "ignore_case"],
    },
    "compose": {
        "label": "Plantilla (literal / value / field / seq)",
        "scope": SCOPE_FIELD,
        "priority": "P2",
        "params_schema": [
            "template",
            "seq_start",
            "seq_step",
            "seq_width",
            "seq_pad_char",
        ],
    },
    "dedupe_rows": {
        "label": "Eliminar filas duplicadas",
        "scope": SCOPE_GLOBAL,
        "priority": "P2",
        "params_schema": ["key_fields"],
    },
    "encoding_normalize": {
        "label": "Forzar encoding / quitar BOM",
        "scope": SCOPE_FILE,
        "priority": "P2",
        "params_schema": ["target_encoding", "strip_bom"],
    },
}

ALLOWED_CODES = frozenset(RULE_CATALOG.keys())


def catalog_choices() -> list[dict]:
    rows = []
    for code, meta in RULE_CATALOG.items():
        rows.append(
            {
                "code": code,
                "label": meta["label"],
                "scope": meta["scope"],
                "priority": meta["priority"],
            }
        )
    return rows


def scope_for(code: str) -> str:
    meta = RULE_CATALOG.get(code) or {}
    return meta.get("scope") or SCOPE_FIELD


def scope_label(scope: str) -> str:
    return {
        SCOPE_FIELD: "campo",
        SCOPE_GLOBAL: "global",
        SCOPE_FILE: "archivo",
    }.get(scope, scope)


def params_summary(code: str, params: dict | None) -> str:
    params = params or {}
    if code == "replace_map":
        mapping = params.get("map") or {}
        if isinstance(mapping, dict) and mapping:
            sample = ", ".join(f"{k}→{v}" for k, v in list(mapping.items())[:3])
            more = "…" if len(mapping) > 3 else ""
            return f"Match exacto · {sample}{more}"
        return "Mapa vacío"
    if code == "replace":
        find = params.get("find", "")
        repl = params.get("replace", "")
        return f'find: "{find}" → "{repl}"'
    if code == "compose":
        return f'template: "{params.get("template", "")}"'
    if code == "null_tokens":
        tokens = params.get("tokens") or ["N/A", "null", "—", ""]
        return ", ".join(str(t) if t != "" else '""' for t in tokens[:4]) + " → vacío"
    if code == "date_normalize":
        inp = params.get("input_formats") or []
        out = params.get("output_format") or "%Y-%m-%d"
        left = ", ".join(inp[:2]) if inp else "auto"
        return f"{left} → {out}"
    if code == "number_normalize":
        return (
            f"decimal={params.get('decimal_sep', '.')} · "
            f"miles={params.get('thousands_sep', ',')}"
        )
    if code == "dedupe_rows":
        keys = params.get("key_fields") or []
        return "clave: " + ("+".join(keys) if keys else "—")
    if code == "encoding_normalize":
        enc = params.get("target_encoding") or "utf-8"
        bom = " · quitar BOM" if params.get("strip_bom", True) else ""
        return f"forzar {enc}{bom}"
    meta = RULE_CATALOG.get(code) or {}
    return meta.get("label") or code
