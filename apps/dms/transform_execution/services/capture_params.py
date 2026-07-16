"""Normalización de parámetros capture_start / capture_end (line vs value)."""

from __future__ import annotations

LINE_MODES = frozenset({"line_number", "line_or_eof"})
PERCENT_MODE = "percent"


def _as_int(raw) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def capture_line(capture: dict | None) -> int | None:
    """Número de línea 1-based. Acepta `line` (canónico) o `value` (legacy)."""
    capture = capture or {}
    for key in ("line", "value"):
        value = _as_int(capture.get(key))
        if value is not None:
            return value
    return None


def capture_percent(capture: dict | None) -> int | None:
    """Porcentaje 1–100. Acepta `value` (canónico) o `line` (legacy)."""
    capture = capture or {}
    for key in ("value", "line"):
        value = _as_int(capture.get(key))
        if value is not None:
            return value
    return None


def normalize_capture(capture: dict | None) -> dict:
    """
    Unifica claves según modo:
    - line_number / line_or_eof → solo `line`
    - percent → solo `value`
    """
    if not capture:
        return {}
    data = dict(capture)
    mode = (data.get("mode") or "").strip()
    if mode in LINE_MODES:
        line = capture_line(data)
        data.pop("value", None)
        if line is not None:
            data["line"] = line
        else:
            data.pop("line", None)
    elif mode == PERCENT_MODE:
        percent = capture_percent(data)
        data.pop("line", None)
        if percent is not None:
            data["value"] = percent
        else:
            data.pop("value", None)
    return data
