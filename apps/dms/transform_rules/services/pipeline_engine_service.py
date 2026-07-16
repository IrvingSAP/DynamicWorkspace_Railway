"""Motor apply_pipeline (transform_rules.md) — usado por preview y ejecución."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from apps.dms.transform_rules.services.transform_catalog_service import (
    ALL_TRANSFORM_OPS,
    active_transform_op_codes,
    normalize_pipeline,
)


class PipelineApplyError(Exception):
    def __init__(self, message: str, *, op: str = "", error_code: str = "pipeline_error"):
        super().__init__(message)
        self.op = op
        self.error_code = error_code


def _is_empty(value) -> bool:
    return value is None or value == ""


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def apply_step(value, step: dict):
    op = (step.get("op") or "").strip()
    allowed = active_transform_op_codes()
    if op not in allowed and op not in ALL_TRANSFORM_OPS:
        raise PipelineApplyError(
            f"Operación «{op}» no habilitada.",
            op=op,
            error_code="op_unknown",
        )
    if op not in allowed:
        raise PipelineApplyError(
            f"Operación «{op}» no habilitada.",
            op=op,
            error_code="op_unknown",
        )

    if op == "trim":
        return _as_text(value).strip()
    if op == "ltrim":
        return _as_text(value).lstrip()
    if op == "rtrim":
        return _as_text(value).rstrip()
    if op == "upper":
        return _as_text(value).upper()
    if op == "lower":
        return _as_text(value).lower()
    if op == "default_if_empty":
        if _is_empty(value):
            return step.get("value", "")
        return value
    if op == "coalesce":
        if not _is_empty(value):
            return value
        for candidate in step.get("values") or step.get("fields") or []:
            if not _is_empty(candidate):
                return candidate
        if "value" in step and not _is_empty(step.get("value")):
            return step.get("value")
        return ""
    if op == "pad_left":
        text = _as_text(value)
        length = int(step.get("length") or 0)
        char = (step.get("char") or " ")[:1] or " "
        if length <= 0 or len(text) >= length:
            return text
        return text.rjust(length, char)
    if op == "pad_right":
        text = _as_text(value)
        length = int(step.get("length") or 0)
        char = (step.get("char") or " ")[:1] or " "
        if length <= 0 or len(text) >= length:
            return text
        return text.ljust(length, char)
    if op == "substring":
        text = _as_text(value)
        start = int(step.get("start") or 0)
        length = step.get("length")
        if start < 0:
            start = 0
        if length in (None, ""):
            return text[start:]
        length_i = int(length)
        if length_i < 0:
            length_i = 0
        return text[start : start + length_i]
    if op == "replace_map":
        text = _as_text(value)
        mapping = step.get("map") or {}
        if text in mapping:
            return mapping[text]
        return text
    if op == "replace":
        text = _as_text(value)
        find = step.get("find")
        if find is None:
            raise PipelineApplyError(
                "replace requiere find.",
                op=op,
                error_code="op_params",
            )
        repl = "" if step.get("replace") is None else str(step.get("replace"))
        find_s = str(find)
        if step.get("regex"):
            try:
                return re.sub(find_s, repl, text)
            except re.error as exc:
                raise PipelineApplyError(
                    f"replace regex inválido: {exc}",
                    op=op,
                    error_code="op_params",
                ) from exc
        return text.replace(find_s, repl)
    if op == "regex_extract":
        text = _as_text(value)
        pattern = str(step.get("pattern") or "")
        group = int(step.get("group") or 0)
        try:
            match = re.search(pattern, text)
        except re.error as exc:
            raise PipelineApplyError(
                f"regex_extract patrón inválido: {exc}",
                op=op,
                error_code="op_params",
            ) from exc
        if not match:
            return ""
        try:
            return match.group(group) or ""
        except IndexError as exc:
            raise PipelineApplyError(
                f"regex_extract grupo {group} no existe.",
                op=op,
                error_code="op_params",
            ) from exc
    if op == "number_format":
        text = _as_text(value).strip()
        if not text:
            return text
        try:
            number = Decimal(text.replace(",", ""))
        except (InvalidOperation, ValueError) as exc:
            raise PipelineApplyError(
                f"No se pudo interpretar el número «{text}».",
                op=op,
                error_code="number_parse",
            ) from exc
        places = int(step.get("decimal_places") if step.get("decimal_places") is not None else 2)
        if places < 0:
            places = 0
        quant = Decimal("1").scaleb(-places) if places else Decimal("1")
        number = number.quantize(quant)
        sign = "-" if number < 0 else ""
        number = abs(number)
        raw = f"{number:.{places}f}" if places else str(int(number))
        int_part, _, frac = raw.partition(".")
        thousands = step.get("thousands_sep")
        if thousands is None:
            thousands = ""
        else:
            thousands = str(thousands)
        decimal_sep = step.get("decimal_sep")
        if decimal_sep is None:
            decimal_sep = "."
        else:
            decimal_sep = str(decimal_sep)
        if thousands:
            grouped = []
            while int_part:
                grouped.insert(0, int_part[-3:])
                int_part = int_part[:-3]
            int_part = thousands.join(grouped)
        if places:
            return f"{sign}{int_part}{decimal_sep}{frac}"
        return f"{sign}{int_part}"
    if op == "boolean_map":
        text = _as_text(value).strip().lower()
        true_values = [str(item).strip().lower() for item in (step.get("true_values") or [])]
        false_values = [str(item).strip().lower() for item in (step.get("false_values") or [])]
        if not true_values:
            true_values = ["1", "true", "t", "yes", "y", "si", "sí"]
        if not false_values:
            false_values = ["0", "false", "f", "no", "n"]
        out_true = step.get("output_true")
        out_false = step.get("output_false")
        if out_true is None:
            out_true = "true"
        if out_false is None:
            out_false = "false"
        if text in true_values:
            return out_true
        if text in false_values:
            return out_false
        return value
    if op == "date_format":
        fmt = (step.get("format") or "").strip()
        if not fmt:
            raise PipelineApplyError(
                "date_format requiere format.",
                op=op,
                error_code="op_params",
            )
        text = _as_text(value).strip()
        if not text:
            return text
        input_formats = list(step.get("input_formats") or [])
        candidates = input_formats + [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
        ]
        parsed = None
        for candidate in candidates:
            try:
                parsed = datetime.strptime(text, candidate)
                break
            except ValueError:
                continue
        if parsed is None:
            raise PipelineApplyError(
                f"No se pudo interpretar la fecha «{text}».",
                op=op,
                error_code="date_parse",
            )
        return parsed.strftime(fmt)

    raise PipelineApplyError(f"Operación «{op}» no implementada.", op=op)


def apply_pipeline(value, steps: list, *, raise_on_error: bool = True):
    """
    Aplica el pipeline en orden.
    Si raise_on_error=False, ante fallo retorna (original_or_partial, error_message).
    """
    current = value
    pipeline = normalize_pipeline(steps)
    for step in pipeline:
        try:
            current = apply_step(current, step)
        except PipelineApplyError as exc:
            if raise_on_error:
                raise
            return current, str(exc)
    if raise_on_error:
        return current
    return current, None
