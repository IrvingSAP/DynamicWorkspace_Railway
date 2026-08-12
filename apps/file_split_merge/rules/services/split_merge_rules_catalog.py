"""Catálogo de reglas Split/Merge (MVP)."""

from __future__ import annotations

OPERATION_SPLIT = "split"
OPERATION_MERGE = "merge"
OPERATIONS = (OPERATION_SPLIT, OPERATION_MERGE)

OPERATION_LABELS = {
    OPERATION_SPLIT: "Split (partir)",
    OPERATION_MERGE: "Merge (unir)",
}

# Codes that count toward Split rules_complete
SPLIT_PARTITION_CODES = frozenset({"max_rows", "max_bytes", "split_by_column"})

RULE_CATALOG = {
    "max_rows": {
        "label": "Partir cada N filas",
        "operation": OPERATION_SPLIT,
        "params_schema": ("n",),
    },
    "max_bytes": {
        "label": "Partir por tamaño aproximado",
        "operation": OPERATION_SPLIT,
        "params_schema": ("bytes",),
    },
    "split_by_column": {
        "label": "Una parte por valor de campo",
        "operation": OPERATION_SPLIT,
        "params_schema": ("field_name", "include_empty"),
    },
    "keep_header": {
        "label": "Repetir encabezado en cada parte",
        "operation": OPERATION_SPLIT,
        "params_schema": ("value",),
    },
    "append": {
        "label": "Concatenar filas (explícito)",
        "operation": OPERATION_MERGE,
        "params_schema": (),
    },
    "missing_columns": {
        "label": "Política columnas faltantes",
        "operation": OPERATION_MERGE,
        "params_schema": ("mode",),
    },
    "dedupe_rows": {
        "label": "Deduplicar tras unir",
        "operation": OPERATION_MERGE,
        "params_schema": ("keys", "keep"),
    },
    "include_header": {
        "label": "Encabezado en salida",
        "operation": OPERATION_MERGE,
        "params_schema": ("value",),
    },
}

ALLOWED_CODES = frozenset(RULE_CATALOG.keys())


def catalog_choices(operation: str | None = None) -> list[dict]:
    rows = []
    for code, meta in RULE_CATALOG.items():
        if operation and meta["operation"] != operation:
            continue
        rows.append(
            {
                "code": code,
                "label": meta["label"],
                "operation": meta["operation"],
            }
        )
    return rows


def operation_for_code(code: str) -> str | None:
    meta = RULE_CATALOG.get(code)
    return meta["operation"] if meta else None


def params_summary(code: str, params: dict | None) -> str:
    params = params or {}
    if code == "max_rows":
        return f"n = {params.get('n', '—')}"
    if code == "max_bytes":
        return f"bytes = {params.get('bytes', '—')}"
    if code == "split_by_column":
        empty = "sí" if params.get("include_empty") else "no"
        return f"campo {params.get('field_name') or '—'} · vacíos: {empty}"
    if code == "keep_header":
        return f"value = {bool(params.get('value', True))}"
    if code == "append":
        return "—"
    if code == "missing_columns":
        return f"mode = {params.get('mode') or 'error'}"
    if code == "dedupe_rows":
        keys = params.get("keys") or []
        return f"keys: {', '.join(keys) if keys else '—'} · keep {params.get('keep') or 'first'}"
    if code == "include_header":
        return f"value = {bool(params.get('value', True))}"
    return "—"
