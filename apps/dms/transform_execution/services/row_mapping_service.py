"""Aplicación de FieldMapping + transform_pipeline por fila."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from apps.dms.transform_rules.services.pipeline_engine_service import (
    PipelineApplyError,
    apply_pipeline,
)


class MappingError(Exception):
    def __init__(self, message: str, *, field: str = "", code: str = "MAPPING_ERROR"):
        super().__init__(message)
        self.field = field
        self.code = code


class GeneratorState:
    """Estado de secuencias por job; scope project usa store de clase (proceso)."""

    _project_counters: dict[str, int] = {}
    _project_job_counters: dict[str, int] = {}

    def __init__(self, *, project_id: str | None = None):
        self.counters: dict[str, int] = {}
        self.job_counter = 0
        self.project_id = str(project_id or "").strip()

    def next_sequence(
        self,
        key: str,
        start: int = 1,
        step: int = 1,
        *,
        scope: str = "job",
        reset_per_job: bool = True,
    ) -> int:
        scope = (scope or "job").strip().lower()
        if scope not in {"row", "job", "project"}:
            scope = "job"
        use_project = scope == "project" or not reset_per_job
        if use_project:
            store = GeneratorState._project_counters
            full_key = f"{self.project_id or '_'}:{key}"
        else:
            store = self.counters
            full_key = key
        if full_key not in store:
            store[full_key] = int(start)
        value = store[full_key]
        store[full_key] = value + int(step)
        return value

    def next_job_counter(self, *, scope: str = "job", reset_per_job: bool = True) -> int:
        scope = (scope or "job").strip().lower()
        use_project = scope == "project" or not reset_per_job
        if use_project:
            key = self.project_id or "_"
            GeneratorState._project_job_counters[key] = (
                GeneratorState._project_job_counters.get(key, 0) + 1
            )
            return GeneratorState._project_job_counters[key]
        self.job_counter += 1
        return self.job_counter


def _is_empty(value) -> bool:
    return value is None or value == ""


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        raise MappingError("Valor numérico vacío en expresión.", code="EXPRESSION_INVALID")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MappingError(
            f"No se pudo convertir «{value}» a número.",
            code="EXPRESSION_INVALID",
        ) from exc


def _eval_expression(node: dict, source_row: dict, *, depth: int = 0):
    if not isinstance(node, dict) or depth > 5:
        raise MappingError("Expresión inválida.", code="EXPRESSION_INVALID")
    if "field" in node:
        return source_row.get(str(node.get("field") or "").strip().lower(), "")
    if "literal" in node:
        return node.get("literal")
    op = (node.get("op") or "").strip()
    left = _eval_expression(node.get("left") or {}, source_row, depth=depth + 1)
    right = _eval_expression(node.get("right") or {}, source_row, depth=depth + 1)

    if op == "concat":
        return f"{'' if left is None else left}{'' if right is None else right}"
    if op == "coalesce":
        return right if _is_empty(left) else left
    left_n = _to_decimal(left)
    right_n = _to_decimal(right)
    if op == "add":
        return left_n + right_n
    if op == "subtract":
        return left_n - right_n
    if op == "multiply":
        return left_n * right_n
    if op == "divide":
        if right_n == 0:
            raise MappingError("División por cero en expression.", code="EXPRESSION_DIVIDE_BY_ZERO")
        return left_n / right_n
    raise MappingError(f"Operador «{op or '—'}» no soportado.", code="EXPRESSION_INVALID")


def _apply_split(value, split: dict) -> str:
    text = "" if value is None else str(value)
    part = (split.get("part") or "").strip()
    if part == "first_word":
        pieces = text.split(None, 1)
        return pieces[0] if pieces else ""
    if part == "rest":
        pieces = text.split(None, 1)
        return pieces[1] if len(pieces) > 1 else ""
    if part == "delimiter":
        delim = split.get("delimiter")
        if delim is None:
            delim = " "
        else:
            delim = str(delim)
        index = int(split.get("index") or 0)
        pieces = text.split(delim) if delim != "" else list(text)
        if index < 0 or index >= len(pieces):
            return ""
        return pieces[index]
    if part == "substring":
        start = int(split.get("start") or 0)
        length = int(split.get("length") or 0)
        if start < 0:
            start = 0
        if length < 0:
            length = 0
        return text[start : start + length]
    if part == "regex":
        pattern = str(split.get("pattern") or "")
        group = int(split.get("group") or 0)
        try:
            match = re.search(pattern, text)
        except re.error as exc:
            raise MappingError(
                f"Patrón regex inválido: {exc}",
                code="SPLIT_REGEX_INVALID",
            ) from exc
        if not match:
            return ""
        try:
            return match.group(group) or ""
        except IndexError as exc:
            raise MappingError(
                f"Grupo regex {group} no existe.",
                code="SPLIT_REGEX_GROUP",
            ) from exc
    raise MappingError(
        f"Parte de split «{part or '—'}» no soportada.",
        code="SPLIT_PART_UNSUPPORTED",
    )


def resolve_mapping_value(
    mapping: dict,
    source_row: dict,
    *,
    row_number: int,
    generators: GeneratorState,
    now: datetime | None = None,
):
    kind = (mapping.get("mapping_kind") or "direct").strip()
    when = now or datetime.now()

    if kind == "direct":
        fields = mapping.get("source_fields") or []
        if not fields:
            return ""
        return source_row.get(fields[0], "")
    if kind == "constant":
        return mapping.get("value", "")
    if kind == "concat":
        parts = []
        for part in mapping.get("parts") or []:
            if part.get("type") == "literal":
                parts.append(str(part.get("value") or ""))
            elif part.get("type") == "field":
                parts.append(str(source_row.get(part.get("name") or "", "") or ""))
        return "".join(parts)
    if kind == "generated":
        return _generate(mapping.get("generator") or {}, row_number, generators, when)
    if kind == "split":
        fields = mapping.get("source_fields") or []
        if not fields:
            return ""
        return _apply_split(source_row.get(fields[0], ""), mapping.get("split") or {})
    if kind == "expression":
        value = _eval_expression(mapping.get("expression") or {}, source_row)
        if isinstance(value, Decimal):
            if value == value.to_integral_value():
                return str(int(value))
            return format(value.normalize(), "f")
        return value
    raise MappingError(
        f"mapping_kind «{kind}» no habilitado en ejecución.",
        field=mapping.get("target_field") or "",
        code="MAPPING_KIND_UNSUPPORTED",
    )


def _format_seq_template(template: str, value: int, pad_char: str = "0") -> str:
    text = str(template or "{seq}")

    def _pad_match(match: re.Match) -> str:
        width = int(match.group(1))
        return str(value).rjust(width, pad_char)

    text = re.sub(r"\{seq:(\d+)\}", _pad_match, text)
    return text.replace("{seq}", str(value))


def _generate(generator: dict, row_number: int, state: GeneratorState, when: datetime):
    gtype = (generator.get("type") or "").strip()
    prefix = str(generator.get("prefix") or "")
    suffix = str(generator.get("suffix") or "")
    start = int(generator.get("start") or 1)
    step = int(generator.get("step") or 1)
    pad_length = int(generator.get("pad_length") or 0)
    pad_char = str(generator.get("pad_char") or "0")[:1] or "0"
    scope = str(generator.get("scope") or "job").strip().lower() or "job"
    reset_raw = generator.get("reset_per_job")
    reset_per_job = True if reset_raw is None else bool(reset_raw)

    if gtype == "unique_uuid":
        return str(uuid.uuid4())
    if gtype == "row_number":
        return str(row_number)
    if gtype == "job_timestamp":
        return when.strftime("%Y-%m-%dT%H:%M:%S")
    if gtype == "unique_job_counter":
        if scope == "row":
            return str(start + (max(1, int(row_number)) - 1) * step)
        return str(state.next_job_counter(scope=scope, reset_per_job=reset_per_job))
    if gtype in {"sequence_numeric", "sequence_padded", "sequence_alphanumeric", "sequence_template"}:
        if scope == "row":
            value = start + (max(1, int(row_number)) - 1) * step
        else:
            key = f"{gtype}:{prefix}:{suffix}:{start}:{step}:{pad_length}:{generator.get('template') or ''}"
            value = state.next_sequence(
                key,
                start=start,
                step=step,
                scope=scope,
                reset_per_job=reset_per_job,
            )
        if gtype == "sequence_template":
            template = str(generator.get("template") or "{seq}")
            return _format_seq_template(template, value, pad_char=pad_char)
        text = str(value)
        if gtype == "sequence_padded" or pad_length > 0:
            width = pad_length or 5
            text = text.rjust(width, pad_char)
        return f"{prefix}{text}{suffix}"
    raise MappingError(
        f"Generador «{gtype or '—'}» no soportado.",
        code="GENERATOR_UNSUPPORTED",
    )


def map_row(
    source_row: dict,
    mappings: list[dict],
    target_fields: list[dict],
    *,
    row_number: int,
    generators: GeneratorState,
) -> tuple[dict, list[dict]]:
    """
    Retorna (target_row, errors).
    errors: [{line, field, code, message, value}]
    """
    errors: list[dict] = []
    target_row: dict = {}
    target_by_name = {
        (field.get("name") or "").strip().lower(): field
        for field in (target_fields or [])
        if (field.get("name") or "").strip()
    }
    active = [m for m in (mappings or []) if m.get("is_active", True)]

    for mapping in active:
        target = (mapping.get("target_field") or "").strip().lower()
        if not target:
            continue
        try:
            value = resolve_mapping_value(
                mapping, source_row, row_number=row_number, generators=generators
            )
            pipeline = mapping.get("transform_pipeline") or []
            if pipeline:
                value = apply_pipeline(value, pipeline, raise_on_error=True)
            target_row[target] = "" if value is None else value
        except (MappingError, PipelineApplyError) as exc:
            errors.append(
                {
                    "line": row_number,
                    "field": target,
                    "code": getattr(exc, "code", None)
                    or getattr(exc, "error_code", None)
                    or "TRANSFORM_ERROR",
                    "message": str(exc),
                    "value": source_row.get((mapping.get("source_fields") or [None])[0]),
                }
            )
            target_row[target] = ""

    # Defaults for unmapped required fields
    for name, field in target_by_name.items():
        if name in target_row:
            continue
        default = field.get("default_value")
        if default not in (None, ""):
            target_row[name] = default
        elif field.get("required"):
            errors.append(
                {
                    "line": row_number,
                    "field": name,
                    "code": "TARGET_REQUIRED_EMPTY",
                    "message": f"Campo destino obligatorio «{name}» sin valor.",
                    "value": "",
                }
            )
            target_row[name] = ""
        else:
            target_row[name] = ""

    # Required validation after defaults
    for name, field in target_by_name.items():
        if not field.get("required"):
            continue
        if _is_empty(target_row.get(name)):
            already = any(
                err.get("field") == name
                and err.get("code") in {"REQUIRED_EMPTY", "TARGET_REQUIRED_EMPTY"}
                for err in errors
            )
            if not already:
                errors.append(
                    {
                        "line": row_number,
                        "field": name,
                        "code": "TARGET_REQUIRED_EMPTY",
                        "message": f"Campo destino obligatorio «{name}» vacío.",
                        "value": target_row.get(name),
                    }
                )

    return target_row, errors
