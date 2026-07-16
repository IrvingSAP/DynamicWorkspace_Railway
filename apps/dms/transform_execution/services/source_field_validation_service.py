"""Validación de campos SourceProfile en ejecución (source_definition.md)."""

from __future__ import annotations

import re
from datetime import datetime

CONTENT_TYPE_PATTERNS = {
    "alphanumeric": re.compile(r"^[A-Za-z0-9]+$"),
    "alpha": re.compile(r"^[A-Za-z]+$"),
    "numeric": re.compile(r"^[0-9]+$"),
    "decimal": re.compile(r"^[0-9]+(\.[0-9]+)?$"),
    "alphanumeric_spaces": re.compile(r"^[A-Za-z0-9 ]+$"),
}

DATE_FORMAT_MAP = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "YYYYMMDD": "%Y%m%d",
    "DD-MM-YYYY": "%d-%m-%Y",
}


def _decode_excluded_char(raw) -> str:
    text = str(raw)
    if text.startswith("\\x") and len(text) >= 4:
        try:
            return chr(int(text[2:], 16))
        except ValueError:
            return text
    if text in {"\\t", "\\n", "\\r", "\\0"}:
        return {
            "\\t": "\t",
            "\\n": "\n",
            "\\r": "\r",
            "\\0": "\x00",
        }[text]
    return text


def line_content_rule_errors(line: str, rules: dict | None, *, line_no: int) -> list[dict]:
    rules = rules or {}
    errors: list[dict] = []
    for raw in rules.get("excluded_chars") or []:
        char = _decode_excluded_char(raw)
        if char and char in line:
            errors.append(
                {
                    "line": line_no,
                    "field": "",
                    "code": "FORBIDDEN_CHAR",
                    "message": f"La línea contiene un carácter prohibido ({raw!r}).",
                    "value": "",
                    "char": str(raw),
                }
            )
            break
    for pattern in rules.get("forbidden_patterns") or []:
        try:
            if re.search(pattern, line):
                errors.append(
                    {
                        "line": line_no,
                        "field": "",
                        "code": "FORBIDDEN_PATTERN",
                        "message": f"La línea coincide con patrón prohibido ({pattern}).",
                        "value": "",
                        "pattern": pattern,
                    }
                )
                break
        except re.error:
            continue
    return errors


def _matches_date(value: str, date_format: str) -> bool:
    fmt = DATE_FORMAT_MAP.get((date_format or "").strip(), date_format or "")
    if not fmt:
        return True
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def validate_field_value(field: dict, value: str, *, line_no: int) -> list[dict]:
    name = (field.get("name") or "").strip()
    text = "" if value is None else str(value)
    errors: list[dict] = []

    if field.get("required") and not text.strip():
        errors.append(
            {
                "line": line_no,
                "field": name,
                "code": "REQUIRED_FIELD_EMPTY",
                "message": f"Campo «{name}» obligatorio vacío.",
                "value": text,
            }
        )
        return errors

    if not text.strip() and not field.get("required"):
        return errors

    content_type = (field.get("content_type") or "").strip()
    if content_type in CONTENT_TYPE_PATTERNS:
        if not CONTENT_TYPE_PATTERNS[content_type].fullmatch(text):
            errors.append(
                {
                    "line": line_no,
                    "field": name,
                    "code": "CONTENT_TYPE_MISMATCH",
                    "message": f"Valor no cumple content_type «{content_type}».",
                    "value": text,
                    "content_type": content_type,
                }
            )
    elif content_type in {"date", "datetime"}:
        if not _matches_date(text, field.get("date_format") or ""):
            errors.append(
                {
                    "line": line_no,
                    "field": name,
                    "code": "CONTENT_TYPE_MISMATCH",
                    "message": (
                        f"Fecha/hora inválida para formato "
                        f"«{field.get('date_format') or '—'}»."
                    ),
                    "value": text,
                }
            )
    elif content_type == "custom":
        pattern = (field.get("pattern") or "").strip()
        if pattern:
            try:
                if not re.fullmatch(pattern, text):
                    errors.append(
                        {
                            "line": line_no,
                            "field": name,
                            "code": "PATTERN_MISMATCH",
                            "message": f"No cumple pattern «{pattern}».",
                            "value": text,
                            "pattern": pattern,
                        }
                    )
            except re.error:
                pass

    pattern = (field.get("pattern") or "").strip()
    if content_type != "custom" and pattern:
        try:
            if not re.fullmatch(pattern, text):
                errors.append(
                    {
                        "line": line_no,
                        "field": name,
                        "code": "PATTERN_MISMATCH",
                        "message": f"No cumple pattern «{pattern}».",
                        "value": text,
                        "pattern": pattern,
                    }
                )
        except re.error:
            pass

    return errors


def validate_row(fields: list[dict], row: dict, *, line_no: int) -> list[dict]:
    errors: list[dict] = []
    for field in fields or []:
        name = (field.get("name") or "").strip()
        if not name:
            continue
        errors.extend(validate_field_value(field, row.get(name, ""), line_no=line_no))
    return errors


def required_line_length(fields: list[dict]) -> int | None:
    max_end = 0
    found = False
    for field in fields or []:
        end = field.get("end")
        start = field.get("start")
        length = field.get("length")
        try:
            if end is not None:
                max_end = max(max_end, int(end))
                found = True
            elif start is not None and length is not None:
                max_end = max(max_end, int(start) + int(length) - 1)
                found = True
        except (TypeError, ValueError):
            continue
    return max_end if found else None
