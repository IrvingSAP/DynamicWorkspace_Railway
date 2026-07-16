"""Opciones de catálogo para los pasos 1–3 del asistente SourceProfile."""

from apps.dms.constants import APPLIES_BOTH, APPLIES_END, APPLIES_START, PHASE_2, PHASE_MVP
from apps.dms.models import CaptureBoundaryMode, CharsetEncoding, LineEnding, SourceFileType

FILE_TYPE_HINTS = {
    "txt_fixed": "Ancho fijo por columnas",
    "txt_delimited": "Separador configurable",
    "csv": "Valores separados",
    "xlsx": "Hoja .xlsx",
    "json": "Documento JSON",
    "xml": "Documento XML",
}

CAPTURE_MODE_HINTS = {
    "first": "Empieza en línea 1 — archivo sin encabezado irrelevante",
    "line_number": "Número de línea 1-based — útil para saltar metadata inicial",
    "after_header_block": "Saltar N líneas iniciales — ej. cabecera corporativa",
    "after_pattern": "Iniciar cuando una línea coincide con regex",
    "after_blank_run": "Tras N líneas en blanco (vacío = solo espacios) — inicia en la siguiente",
    "marker_start": "Texto literal que indica inicio — ej. === DATOS ===",
    "eof": "Hasta la última línea — caso más común",
    "percent": "Procesar hasta X % de líneas totales — ej. 80 % para pruebas parciales",
    "max_rows": "Tras leer N filas de datos, parar — ej. primeras 1000 filas",
    "before_pattern": "Detener cuando aparece regex — ej. ^TOTAL en footer",
    "marker_end": "Detener al encontrar texto literal — ej. === FIN ===",
    "blank_run": "Detener ante N líneas en blanco consecutivas (vacío = solo espacios)",
    "line_or_eof": "Línea N o final del archivo, lo que ocurra primero",
}


def _phase_badge(phase: str) -> str:
    if phase == PHASE_MVP:
        return "MVP"
    if phase == PHASE_2:
        return "Fase 2"
    return phase


def _file_type_item(item: SourceFileType) -> dict:
    return {
        "code": item.code,
        "name": item.name,
        "hint": item.description or FILE_TYPE_HINTS.get(item.code, ""),
        "phase": item.phase,
        "disabled": False,
        "badge": _phase_badge(item.phase),
    }


def _encoding_item(item: CharsetEncoding) -> dict:
    return {
        "code": item.code,
        "name": item.name,
        "is_auto_detect": item.is_auto_detect,
    }


def _line_ending_item(item: LineEnding) -> dict:
    return {
        "code": item.code,
        "name": item.name,
        "allows_custom_value": item.allows_custom_value,
        "is_auto_detect": item.is_auto_detect,
    }


def _boundary_mode_item(item: CaptureBoundaryMode) -> dict:
    return {
        "code": item.code,
        "name": item.name,
        "hint": item.description or CAPTURE_MODE_HINTS.get(item.code, ""),
        "phase": item.phase,
        "disabled": False,
        "badge": _phase_badge(item.phase) if item.phase == PHASE_2 else "",
    }


def _fallback_file_types() -> list[dict]:
    return [
        {
            "code": code,
            "name": name,
            "hint": FILE_TYPE_HINTS.get(code, ""),
            "phase": PHASE_MVP,
            "disabled": False,
            "badge": "MVP",
        }
        for code, name in [
            ("txt_fixed", "TXT posicional"),
            ("txt_delimited", "TXT delimitado"),
            ("csv", "CSV"),
            ("xlsx", "Excel"),
            ("json", "JSON"),
            ("xml", "XML"),
        ]
    ]


def _fallback_encodings() -> list[dict]:
    return [
        {"code": "auto", "name": "Detección automática", "is_auto_detect": True},
        {"code": "utf-8", "name": "UTF-8", "is_auto_detect": False},
        {"code": "latin-1", "name": "Latin-1 (ISO-8859-1)", "is_auto_detect": False},
        {"code": "windows-1252", "name": "Windows-1252", "is_auto_detect": False},
    ]


def _fallback_line_endings() -> list[dict]:
    return [
        {"code": "auto", "name": "Detección automática", "allows_custom_value": False, "is_auto_detect": True},
        {"code": "lf", "name": "LF (Unix)", "allows_custom_value": False, "is_auto_detect": False},
        {"code": "crlf", "name": "CRLF (Windows)", "allows_custom_value": False, "is_auto_detect": False},
        {"code": "custom", "name": "Personalizado", "allows_custom_value": True, "is_auto_detect": False},
    ]


def get_file_types() -> list[dict]:
    qs = SourceFileType.objects.filter(is_active=True).order_by("sort_order", "code")
    if qs.exists():
        return [_file_type_item(item) for item in qs]
    return _fallback_file_types()


def get_encodings() -> list[dict]:
    qs = CharsetEncoding.objects.filter(is_active=True).order_by("sort_order", "code")
    if qs.exists():
        return [_encoding_item(item) for item in qs]
    return _fallback_encodings()


def get_line_endings() -> list[dict]:
    qs = LineEnding.objects.filter(is_active=True).order_by("sort_order", "code")
    if qs.exists():
        return [_line_ending_item(item) for item in qs]
    return _fallback_line_endings()


def _fallback_capture_modes(applies: str) -> list[dict]:
    if applies == "start":
        codes = [
            ("first", "Primera línea", PHASE_MVP),
            ("line_number", "Línea específica", PHASE_MVP),
            ("after_header_block", "Tras N líneas iniciales", PHASE_MVP),
            ("after_pattern", "Tras patrón regex", PHASE_MVP),
            ("after_blank_run", "Tras líneas en blanco", PHASE_MVP),
            ("marker_start", "Marcador de inicio", PHASE_MVP),
        ]
    else:
        codes = [
            ("eof", "Final del archivo", PHASE_MVP),
            ("line_number", "Línea específica", PHASE_MVP),
            ("percent", "Porcentaje del archivo", PHASE_MVP),
            ("max_rows", "Máximo de filas", PHASE_MVP),
            ("before_pattern", "Antes de patrón", PHASE_MVP),
            ("marker_end", "Marcador de fin", PHASE_MVP),
            ("blank_run", "Líneas en blanco consecutivas", PHASE_MVP),
            ("line_or_eof", "Línea N o EOF", PHASE_MVP),
        ]
    return [
        {
            "code": code,
            "name": name,
            "hint": CAPTURE_MODE_HINTS.get(code, ""),
            "phase": phase,
            "disabled": False,
            "badge": _phase_badge(phase) if phase == PHASE_2 else "",
        }
        for code, name, phase in codes
    ]


def get_capture_modes(applies: str) -> list[dict]:
    if applies == "start":
        applies_values = (APPLIES_START, APPLIES_BOTH)
    else:
        applies_values = (APPLIES_END, APPLIES_BOTH)

    qs = (
        CaptureBoundaryMode.objects.filter(is_active=True, applies_to__in=applies_values)
        .order_by("sort_order", "code")
    )
    if qs.exists():
        return [_boundary_mode_item(item) for item in qs]
    return _fallback_capture_modes(applies)


def get_step1_catalog_context() -> dict:
    return {
        "file_types": get_file_types(),
        "encodings": get_encodings(),
        "line_endings": get_line_endings(),
    }


def get_step2_catalog_context() -> dict:
    return {
        "capture_start_modes": get_capture_modes("start"),
    }


def get_step3_catalog_context() -> dict:
    return {
        "capture_end_modes": get_capture_modes("end"),
    }
