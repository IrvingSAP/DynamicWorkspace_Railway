"""Motor de reglas File Clean (aplica clean_rules fila a fila)."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime

from apps.file_clean.rules.services import clean_rules_catalog as catalog

COMPOSE_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
INVISIBLE_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad]"
)


@dataclass
class EngineResult:
    rows: list[dict] = field(default_factory=list)
    change_log: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def apply_trim(value: str, _params: dict) -> str:
    return value.strip()


def apply_strip_invisible(value: str, _params: dict) -> str:
    text = INVISIBLE_RE.sub("", value)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def apply_case_upper(value: str, _params: dict) -> str:
    return value.upper()


def apply_case_lower(value: str, _params: dict) -> str:
    return value.lower()


def apply_null_tokens(value: str, params: dict) -> str:
    tokens = params.get("tokens") or ["N/A", "null", "—", ""]
    for token in tokens:
        if value == str(token):
            return ""
    return value


def apply_date_normalize(value: str, params: dict) -> str:
    if not value.strip():
        return value
    formats = params.get("input_formats") or []
    out = params.get("output_format") or "%Y-%m-%d"
    candidates = list(formats) + ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    seen = set()
    for fmt in candidates:
        if not fmt or fmt in seen:
            continue
        seen.add(fmt)
        try:
            return datetime.strptime(value.strip(), fmt).strftime(out)
        except ValueError:
            continue
    return value


def apply_number_normalize(value: str, params: dict) -> str:
    if not value.strip():
        return value
    decimal_sep = params.get("decimal_sep") or "."
    thousands_sep = params.get("thousands_sep") or ","
    text = value.strip()
    if thousands_sep:
        text = text.replace(thousands_sep, "")
    if decimal_sep and decimal_sep != ".":
        text = text.replace(decimal_sep, ".")
    return text


def apply_replace_map(value: str, params: dict) -> str:
    mapping = params.get("map") or {}
    if not isinstance(mapping, dict) or not mapping:
        return value
    case_insensitive = bool(params.get("case_insensitive"))
    if case_insensitive:
        lower_map = {str(k).lower(): str(v) for k, v in mapping.items()}
        return lower_map.get(value.lower(), value)
    return str(mapping[value]) if value in mapping else value


def apply_replace(value: str, params: dict) -> str:
    find = params.get("find")
    if find is None or find == "":
        return value
    repl = "" if params.get("replace") is None else str(params.get("replace"))
    find = str(find)
    all_occ = bool(params.get("all", True))
    ignore_case = bool(params.get("ignore_case"))
    if ignore_case:
        flags = re.IGNORECASE
        pattern = re.escape(find)
        if all_occ:
            return re.sub(pattern, repl, value, flags=flags)
        return re.sub(pattern, repl, value, count=1, flags=flags)
    if all_occ:
        return value.replace(find, repl)
    return value.replace(find, repl, 1)


def apply_compose(value: str, params: dict, *, row: dict, seq: int) -> str:
    template = params.get("template") or ""
    if not template:
        return value

    def repl(match: re.Match) -> str:
        token = match.group(1).strip()
        if token == "value":
            return value
        if token == "seq":
            width = params.get("seq_width")
            pad = str(params.get("seq_pad_char") or "0")[:1] or "0"
            text = str(seq)
            if width:
                try:
                    text = text.zfill(int(width)) if pad == "0" else text.rjust(int(width), pad)
                except (TypeError, ValueError):
                    pass
            return text
        if token.startswith("field:"):
            name = token[6:].strip()
            return _as_text(row.get(name, ""))
        return match.group(0)

    return COMPOSE_TOKEN_RE.sub(repl, template)


_FIELD_OPS = {
    "trim": apply_trim,
    "strip_invisible": apply_strip_invisible,
    "case_upper": apply_case_upper,
    "case_lower": apply_case_lower,
    "null_tokens": apply_null_tokens,
    "date_normalize": apply_date_normalize,
    "number_normalize": apply_number_normalize,
    "replace_map": apply_replace_map,
    "replace": apply_replace,
}


def _enabled_rules(rules: list[dict]) -> list[dict]:
    ordered = sorted(
        [r for r in rules if isinstance(r, dict) and r.get("enabled", True)],
        key=lambda r: int(r.get("sort_order") or 0),
    )
    return ordered


def apply_rules(rows: list[dict], rules: list[dict]) -> EngineResult:
    """Apply enabled clean_rules. rows are plain dicts field→value."""
    enabled = _enabled_rules(rules)
    file_rules = [r for r in enabled if catalog.scope_for(r.get("code", "")) == catalog.SCOPE_FILE]
    field_rules = [r for r in enabled if catalog.scope_for(r.get("code", "")) == catalog.SCOPE_FIELD]
    global_rules = [r for r in enabled if catalog.scope_for(r.get("code", "")) == catalog.SCOPE_GLOBAL]

    # encoding_normalize is handled at I/O layer; keep metric note
    encoding_rule = next((r for r in file_rules if r.get("code") == "encoding_normalize"), None)

    change_log: list[dict] = []
    by_code: dict[str, int] = {}
    seq_start = 1
    seq_step = 1
    for rule in field_rules:
        if rule.get("code") == "compose":
            params = rule.get("params") or {}
            try:
                seq_start = int(params.get("seq_start") or 1)
            except (TypeError, ValueError):
                seq_start = 1
            try:
                seq_step = int(params.get("seq_step") or 1)
            except (TypeError, ValueError):
                seq_step = 1
            break

    seq = seq_start
    out_rows: list[dict] = []
    for row_index, original in enumerate(rows, start=1):
        row = deepcopy(original)
        for rule in field_rules:
            code = (rule.get("code") or "").strip()
            field_name = (rule.get("field_name") or "").strip()
            if not field_name:
                continue
            params = rule.get("params") or {}
            before = _as_text(row.get(field_name, ""))
            if code == "compose":
                after = apply_compose(before, params, row=row, seq=seq)
            else:
                fn = _FIELD_OPS.get(code)
                if fn is None:
                    raise ValueError(f"Unsupported clean rule code: {code}")
                after = fn(before, params)
            if after != before:
                row[field_name] = after
                change_log.append(
                    {
                        "row": row_index,
                        "field": field_name,
                        "rule": code,
                        "before": before,
                        "after": after,
                    }
                )
                by_code[code] = by_code.get(code, 0) + 1
        out_rows.append(row)
        seq += seq_step

    dedupe_count = 0
    for rule in global_rules:
        if rule.get("code") != "dedupe_rows":
            continue
        keys = (rule.get("params") or {}).get("key_fields") or []
        if not keys:
            continue
        seen = set()
        unique = []
        for row_index, row in enumerate(out_rows, start=1):
            key = tuple(_as_text(row.get(k, "")) for k in keys)
            if key in seen:
                dedupe_count += 1
                change_log.append(
                    {
                        "row": row_index,
                        "field": "+".join(keys),
                        "rule": "dedupe_rows",
                        "before": "|".join(key),
                        "after": "",
                    }
                )
                by_code["dedupe_rows"] = by_code.get("dedupe_rows", 0) + 1
                continue
            seen.add(key)
            unique.append(row)
        out_rows = unique

    metrics = {
        "rows_read": len(rows),
        "rows_written": len(out_rows),
        "cells_changed": len(
            [c for c in change_log if c.get("rule") != "dedupe_rows"]
        ),
        "dedupe_count": dedupe_count,
        "by_code": by_code,
        "encoding_normalize": bool(encoding_rule),
    }
    return EngineResult(rows=out_rows, change_log=change_log, metrics=metrics)


def encoding_params(rules: list[dict]) -> dict:
    for rule in _enabled_rules(rules):
        if rule.get("code") == "encoding_normalize":
            params = rule.get("params") or {}
            return {
                "target_encoding": (params.get("target_encoding") or "utf-8").strip() or "utf-8",
                "strip_bom": bool(params.get("strip_bom", True)),
            }
    return {}
