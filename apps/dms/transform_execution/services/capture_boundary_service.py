"""Aplicación de capture_start / capture_end sobre líneas de texto."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from apps.dms.transform_execution.services.capture_params import (
    capture_line,
    capture_percent,
    normalize_capture,
)


@dataclass
class CaptureBounds:
    begin: int
    finish: int
    messages: list[dict] = field(default_factory=list)


def _compile_pattern(pattern: str) -> re.Pattern | None:
    text = (pattern or "").strip()
    if not text:
        return None
    try:
        return re.compile(text)
    except re.error:
        return None


def short_file_warning(*, expected_line: int, actual_lines: int) -> dict:
    return {
        "level": "warning",
        "code": "CAPTURE_OUT_OF_RANGE",
        "expected_line": expected_line,
        "actual_lines": actual_lines,
        "text": (
            f"El archivo tiene {actual_lines} línea(s); "
            f"capture_end.line={expected_line} no se alcanzó. "
            f"Se procesó hasta el final del archivo."
        ),
    }


def find_line_bounds(
    lines: list[str],
    capture_start: dict | None,
    capture_end: dict | None,
) -> CaptureBounds:
    """Índices [begin, finish) sobre la lista de líneas."""
    total = len(lines)
    begin = 0
    finish = total
    messages: list[dict] = []

    start = normalize_capture(capture_start)
    end = normalize_capture(capture_end)
    start_mode = (start.get("mode") or "first").strip()
    end_mode = (end.get("mode") or "eof").strip()

    if start_mode == "line_number":
        line = capture_line(start)
        if line is not None:
            begin = max(0, line - 1)
            if line > total:
                messages.append(
                    {
                        "level": "warning",
                        "code": "CAPTURE_OUT_OF_RANGE",
                        "expected_line": line,
                        "actual_lines": total,
                        "text": (
                            f"El archivo tiene {total} línea(s); "
                            f"capture_start.line={line} queda fuera de rango. "
                            f"No hay filas de captura."
                        ),
                    }
                )
    elif start_mode == "after_header_block":
        try:
            skip = int(start.get("skip_lines") or 0)
        except (TypeError, ValueError):
            skip = 0
        begin = min(total, max(0, skip))
    elif start_mode == "marker_start":
        marker = (start.get("marker") or "").strip()
        if marker:
            for index, line_text in enumerate(lines):
                if marker in line_text:
                    begin = index + 1
                    break
    elif start_mode == "after_pattern":
        rx = _compile_pattern(start.get("pattern") or "")
        if rx:
            for index, line_text in enumerate(lines):
                if rx.search(line_text):
                    begin = index + 1
                    break
    elif start_mode == "after_blank_run":
        # Inicio tras la N-ésima blanca (vacío = not line.strip()).
        try:
            blank_count = int(start.get("blank_count") or 1)
        except (TypeError, ValueError):
            blank_count = 1
        blank_count = max(1, blank_count)
        run = 0
        for index, line_text in enumerate(lines):
            if not line_text.strip():
                run += 1
                if run >= blank_count:
                    begin = index + 1
                    break
            else:
                run = 0

    if end_mode == "line_number":
        # B: truncar a EOF + warning si el archivo es más corto que la línea pedida.
        # E: distinto de line_or_eof (que no avisa).
        line = capture_line(end)
        if line is not None:
            if total < line:
                messages.append(
                    short_file_warning(expected_line=line, actual_lines=total)
                )
            finish = min(total, line)
    elif end_mode == "line_or_eof":
        line = capture_line(end)
        if line is not None:
            finish = min(total, line)
    elif end_mode == "percent":
        percent = capture_percent(end)
        if percent is not None:
            finish = min(total, max(begin + 1, int(total * percent / 100)))
    elif end_mode == "marker_end":
        marker = (end.get("marker") or "").strip()
        if marker:
            for index in range(begin, total):
                if marker in lines[index]:
                    finish = index
                    break
    elif end_mode == "before_pattern":
        rx = _compile_pattern(end.get("pattern") or "")
        if rx:
            for index in range(begin, total):
                if rx.search(lines[index]):
                    finish = index
                    break
    elif end_mode == "blank_run":
        # Fin exclusive en la primera blanca del run (vacío = not line.strip()).
        try:
            blank_count = int(end.get("blank_count") or 1)
        except (TypeError, ValueError):
            blank_count = 1
        blank_count = max(1, blank_count)
        run = 0
        for index in range(begin, total):
            if not lines[index].strip():
                run += 1
                if run >= blank_count:
                    finish = index - blank_count + 1
                    break
            else:
                run = 0

    begin = max(0, min(begin, total))
    finish = max(begin, min(finish, total))
    return CaptureBounds(begin=begin, finish=finish, messages=messages)


def apply_row_limit(lines: list, capture_end: dict | None) -> list:
    end = normalize_capture(capture_end)
    if (end.get("mode") or "").strip() != "max_rows":
        return lines
    try:
        max_rows = int(end.get("max_rows"))
    except (TypeError, ValueError):
        return lines
    if max_rows < 1:
        return lines
    return lines[:max_rows]
