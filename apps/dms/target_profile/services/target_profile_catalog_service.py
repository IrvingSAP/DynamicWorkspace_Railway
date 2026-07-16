"""Catálogos para el asistente TargetProfile."""

from apps.dms.constants import PHASE_2, PHASE_MVP
from apps.dms.models import CharsetEncoding, LineEnding, TargetFieldDataType, TargetFileType

FILE_TYPE_HINTS = {
    "txt_fixed": "Ancho fijo por columnas",
    "txt_delimited": "Separado por delimitador",
    "csv": "Valores separados por comas/punto y coma",
    "xlsx": "Hoja de cálculo Excel",
    "json": "Estructura JSON",
    "xml": "Estructura XML",
}

FALLBACK_FILE_TYPES = [
    ("txt_fixed", "TXT posicional", False),
    ("txt_delimited", "TXT delimitado", False),
    ("csv", "CSV", False),
    ("xlsx", "Excel", False),
    ("json", "JSON", False),
    ("xml", "XML", False),
]

FALLBACK_DATA_TYPES = [
    ("string", "Texto"),
    ("integer", "Entero"),
    ("decimal", "Decimal"),
    ("date", "Fecha"),
    ("datetime", "Fecha y hora"),
    ("boolean", "Booleano"),
]


def get_file_types() -> list[dict]:
    rows = list(
        TargetFileType.objects.filter(is_active=True).order_by("sort_order", "code")
    )
    if not rows:
        return [
            {
                "code": code,
                "name": name,
                "hint": FILE_TYPE_HINTS.get(code, ""),
                "disabled": phase2,
                "badge": "Fase 2" if phase2 else "",
            }
            for code, name, phase2 in FALLBACK_FILE_TYPES
        ]
    result = []
    for item in rows:
        phase2 = (item.phase or PHASE_MVP) == PHASE_2
        result.append(
            {
                "code": item.code,
                "name": item.name,
                "hint": FILE_TYPE_HINTS.get(item.code, item.description or ""),
                "disabled": phase2,
                "badge": "Fase 2" if phase2 else "",
            }
        )
    return result


def get_encodings(*, exclude_auto: bool = True) -> list[dict]:
    qs = CharsetEncoding.objects.filter(is_active=True).order_by("sort_order", "code")
    if exclude_auto:
        qs = qs.filter(is_auto_detect=False)
    rows = list(qs)
    if not rows:
        return [
            {"code": "utf-8", "name": "UTF-8"},
            {"code": "latin-1", "name": "Latin-1"},
            {"code": "cp1252", "name": "Windows-1252"},
        ]
    return [{"code": item.code, "name": item.name} for item in rows]


def get_line_endings(*, exclude_auto: bool = True) -> list[dict]:
    qs = LineEnding.objects.filter(is_active=True).order_by("sort_order", "code")
    if exclude_auto:
        qs = qs.filter(is_auto_detect=False)
    rows = list(qs)
    if not rows:
        return [
            {"code": "lf", "name": "LF (Unix)"},
            {"code": "crlf", "name": "CRLF (Windows)"},
        ]
    return [
        {
            "code": item.code,
            "name": item.name,
            "allows_custom": bool(item.allows_custom_value),
        }
        for item in rows
    ]


def get_data_types() -> list[dict]:
    rows = list(
        TargetFieldDataType.objects.filter(is_active=True).order_by("sort_order", "code")
    )
    if not rows:
        return [{"code": code, "name": name} for code, name in FALLBACK_DATA_TYPES]
    return [{"code": item.code, "name": item.name} for item in rows]


def get_step1_catalog_context() -> dict:
    return {"file_types": get_file_types()}


def get_step2_catalog_context() -> dict:
    return {
        "encodings": get_encodings(exclude_auto=True),
        "line_endings": get_line_endings(exclude_auto=True),
    }
