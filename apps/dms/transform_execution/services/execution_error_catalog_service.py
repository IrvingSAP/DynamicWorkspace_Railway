"""Resolución de mensajes de informe desde `ExecutionErrorCode`."""

from __future__ import annotations

from threading import Lock

from django.db.utils import OperationalError, ProgrammingError

# Fallback si el catálogo no está disponible o el código no existe.
# Placeholders: {field} {value} {line} {content_type} {pattern} {char}
#               {actual} {expected} {expected_line} {actual_lines} {detail}
FALLBACK_MESSAGES: dict[str, str] = {
    "CONTENT_TYPE_MISMATCH": "Tipo de contenido inválido{detail}.",
    "REQUIRED_FIELD_EMPTY": "Campo obligatorio vacío{detail}.",
    "PATTERN_MISMATCH": "No cumple el patrón esperado{detail}.",
    "FORBIDDEN_CHAR": "La línea contiene un carácter prohibido{detail}.",
    "FORBIDDEN_PATTERN": "La línea coincide con un patrón prohibido{detail}.",
    "LINE_LENGTH_MISMATCH": "Línea más corta que la definición posicional{detail}.",
    "DELIMITER_MISMATCH": "Columnas inconsistentes{detail}.",
    "CAPTURE_OUT_OF_RANGE": (
        "El archivo tiene {actual_lines} línea(s); "
        "la captura pedía hasta {expected_line}. "
        "Se procesó hasta el final disponible."
    ),
    "TARGET_REQUIRED_EMPTY": "Campo destino obligatorio vacío{detail}.",
    "REQUIRED_EMPTY": "Campo destino obligatorio vacío{detail}.",
    "TARGET_TYPE_MISMATCH": "Tipo destino incompatible{detail}.",
    "TARGET_LENGTH_EXCEEDED": "Supera la longitud máxima{detail}.",
    "TARGET_RECORD_LENGTH_OVERFLOW": "La línea excede la longitud del registro{detail}.",
    "TARGET_PATTERN_MISMATCH": "No cumple el patrón destino{detail}.",
    "TARGET_SERIALIZATION_ERROR": "Error al formatear el valor{detail}.",
    "MAPPING_KIND_UNSUPPORTED": "Tipo de mapeo no soportado{detail}.",
    "GENERATOR_UNSUPPORTED": "Generador no soportado{detail}.",
    "TRANSFORM_ERROR": "Error en transformación{detail}.",
    "JOB_ABORTED": "Ejecución abortada por política.",
    "JOB_STORAGE_ERROR": "Error de almacenamiento.",
    "JOB_INVALID_OUTPUT_PATTERN": "Patrón de nombre de salida inválido.",
}

_CODE_ALIASES: dict[str, str] = {
    "REQUIRED_EMPTY": "TARGET_REQUIRED_EMPTY",
}

_cache: dict[str, dict] | None = None
_cache_lock = Lock()


class _SafeFormat(dict):
    def __missing__(self, key: str) -> str:
        return ""


def invalidate_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def _load_catalog() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    with _cache_lock:
        if _cache is not None:
            return _cache
        entries: dict[str, dict] = {}
        try:
            from apps.dms.models import ExecutionErrorCode

            for item in ExecutionErrorCode.objects.filter(is_active=True).only(
                "code", "name", "description", "severity", "phase"
            ):
                entries[item.code] = {
                    "code": item.code,
                    "name": item.name or "",
                    "description": item.description or "",
                    "severity": item.severity or "error",
                    "phase": item.phase or "parse",
                }
        except (OperationalError, ProgrammingError, ImportError):
            entries = {}
        _cache = entries
        return entries


def get_error_entry(code: str) -> dict | None:
    code = (code or "").strip()
    if not code:
        return None
    catalog = _load_catalog()
    entry = catalog.get(code)
    if entry:
        return entry
    alias = _CODE_ALIASES.get(code)
    if alias:
        return catalog.get(alias)
    return None


def _context_detail(context: dict) -> str:
    field = str(context.get("field") or "").strip()
    content_type = str(context.get("content_type") or "").strip()
    pattern = str(context.get("pattern") or "").strip()
    char = str(context.get("char") or "").strip()
    actual = context.get("actual")
    expected = context.get("expected")
    parts: list[str] = []
    if field:
        parts.append(f"campo «{field}»")
    if content_type:
        parts.append(f"tipo «{content_type}»")
    if pattern:
        parts.append(f"patrón «{pattern}»")
    if char:
        parts.append(f"carácter {char!r}")
    if (
        actual not in (None, "")
        and expected not in (None, "")
    ):
        parts.append(f"{actual} < {expected}")
    if not parts:
        return ""
    return f" ({'; '.join(parts)})"


def _format_template(template: str, ctx: dict) -> str:
    try:
        return template.format_map(_SafeFormat(ctx)).strip()
    except (ValueError, KeyError):
        return template.strip()


def resolve_message(
    code: str,
    *,
    context: dict | None = None,
    fallback: str = "",
) -> str:
    """
    Resuelve el mensaje de usuario para un código de error.

    Prioridad:
    1. `description` del catálogo (plantilla)
    2. fallback del productor (detalle técnico en español)
    3. `name` del catálogo
    4. FALLBACK_MESSAGES
    5. code
    """
    code = (code or "").strip()
    ctx = dict(context or {})
    if "detail" not in ctx:
        ctx["detail"] = _context_detail(ctx)
    for key, value in list(ctx.items()):
        if value is None:
            ctx[key] = ""
        elif not isinstance(value, str):
            ctx[key] = str(value)

    entry = get_error_entry(code)
    description = (entry.get("description") or "").strip() if entry else ""
    if description:
        return _format_template(description, ctx) or fallback or code

    fallback_text = (fallback or "").strip()
    if fallback_text:
        return fallback_text

    name = (entry.get("name") or "").strip() if entry else ""
    if name:
        # Si el nombre no usa placeholders, anexar detail cuando aporte contexto.
        if "{" not in name and ctx.get("detail"):
            return f"{name}{ctx['detail']}".strip()
        return _format_template(name, ctx) or code

    seeded = FALLBACK_MESSAGES.get(code) or FALLBACK_MESSAGES.get(
        _CODE_ALIASES.get(code, ""), ""
    )
    if seeded:
        return _format_template(seeded, ctx) or code
    return code


def _error_context(err: dict) -> dict:
    ctx = {
        "field": err.get("field") or "",
        "value": "" if err.get("value") is None else err.get("value"),
        "line": "" if err.get("line") is None else err.get("line"),
    }
    params = err.get("params")
    if isinstance(params, dict):
        ctx.update(params)
    for key in (
        "content_type",
        "pattern",
        "char",
        "actual",
        "expected",
        "expected_line",
        "actual_lines",
        "detail",
    ):
        if key in err and err[key] is not None:
            ctx[key] = err[key]
    return ctx


def localize_row_error(err: dict) -> dict:
    if not isinstance(err, dict):
        return err
    out = dict(err)
    code = (out.get("code") or "").strip()
    if not code:
        return out
    out["message"] = resolve_message(
        code,
        context=_error_context(out),
        fallback=str(out.get("message") or ""),
    )
    return out


def localize_row_errors(errors: list[dict] | None) -> list[dict]:
    return [localize_row_error(err) for err in (errors or [])]


def localize_report_message(msg: dict) -> dict:
    if not isinstance(msg, dict):
        return msg
    out = dict(msg)
    code = (out.get("code") or "").strip()
    if not code:
        return out
    resolved = resolve_message(
        code,
        context=_error_context(out),
        fallback=str(out.get("text") or out.get("message") or ""),
    )
    out["text"] = resolved
    if "message" in out:
        out["message"] = resolved
    return out


def localize_report_messages(messages: list[dict] | None) -> list[dict]:
    return [localize_report_message(msg) for msg in (messages or [])]
