"""Servicios del asistente SourceProfile (source_definition.md)."""

import copy
import json
from dataclasses import dataclass, field

from apps.dms.models import FieldContentType
from apps.dms.source_profile.services import source_persistence_service

DEFAULT_POSITIONAL_FIELDS = [
    {
        "name": "documento",
        "label": "Documento",
        "start": 1,
        "end": 5,
        "content_type": "numeric",
        "required": True,
        "pattern": "",
    },
    {
        "name": "nombre",
        "label": "Nombre",
        "start": 6,
        "end": 15,
        "content_type": "alpha",
        "required": True,
        "pattern": "",
    },
    {
        "name": "salario",
        "label": "Salario",
        "start": 16,
        "end": 21,
        "content_type": "numeric",
        "required": True,
        "pattern": "",
    },
    {
        "name": "estado",
        "label": "Estado",
        "start": 22,
        "end": 22,
        "content_type": "alphanumeric",
        "required": False,
        "pattern": "",
    },
]


@dataclass
class WizardStepStatus:
    number: int
    slug: str
    title: str
    summary: str
    status: str  # done | draft | pending
    url_name: str


@dataclass
class SourceWizardContext:
    project_name: str
    project_slug: str
    membership_role: str = "—"
    version_label: str = "Borrador"
    version_number: int = 1
    steps_complete: int = 0
    steps_total: int = 6
    file_type_label: str = "—"
    fields_count: int = 0
    steps: list[WizardStepStatus] = field(default_factory=list)
    continue_step_url_name: str = "dms:source_step1"


DEFAULT_CONTENT_RULES = {
    "trim_lines": True,
    "skip_empty_lines": True,
    "comment_prefix": "#",
    "allowed_chars": "",
    "excluded_chars": ["\\x00", "\\x1a"],
    "forbidden_patterns": ["^ERROR"],
}

DEFAULT_PROCESSING_REPORT = {
    "report_enabled": True,
    "include_summary": True,
    "include_row_errors": True,
    "reject_alert_threshold": 10,
    "reject_alert_threshold_unit": "count",
    "report_format": "json",
}

DEFAULT_DELIMITED_CONFIG = {
    "delimiter": ";",
    "quote_char": '"',
    "escape_char": "\\",
    "has_header": True,
    "header_row": 1,
}

DEFAULT_DELIMITED_FIELDS = [
    {
        "name": "documento",
        "source_column": "DOC_ID",
        "column_index": 0,
        "content_type": "numeric",
        "required": True,
    },
    {
        "name": "nombre",
        "source_column": "NOMBRE",
        "column_index": 1,
        "content_type": "alpha",
        "required": True,
    },
    {
        "name": "salario",
        "source_column": "SALARIO",
        "column_index": 2,
        "content_type": "numeric",
        "required": True,
    },
    {
        "name": "estado",
        "source_column": "ESTADO",
        "column_index": 3,
        "content_type": "alphanumeric",
        "required": False,
    },
]

DEFAULT_XLSX_CONFIG = {
    "sheet_name": "Hoja1",
    "header_row": 1,
}

DEFAULT_XLSX_FIELDS = [
    {"name": "documento", "column": "A", "content_type": "numeric", "required": True},
    {"name": "nombre", "column": "B", "content_type": "alpha", "required": True},
    {"name": "salario", "column": "C", "content_type": "numeric", "required": True},
    {"name": "estado", "column": "D", "content_type": "alphanumeric", "required": False},
]

DEFAULT_JSON_CONFIG = {
    "record_path": "empleados",
}

DEFAULT_JSON_FIELDS = [
    {"name": "documento", "json_path": "documento", "content_type": "numeric", "required": True},
    {"name": "nombre", "json_path": "nombre", "content_type": "alpha", "required": True},
    {"name": "salario", "json_path": "salario", "content_type": "numeric", "required": True},
]

DEFAULT_XML_CONFIG = {
    "record_element": "empleado",
}

DEFAULT_XML_FIELDS = [
    {"name": "documento", "element": "documento", "content_type": "numeric", "required": True},
    {"name": "nombre", "element": "nombre", "content_type": "alpha", "required": True},
    {"name": "salario", "element": "salario", "content_type": "numeric", "required": True},
]

FILE_TYPE_FIXED = {"txt_fixed"}
FILE_TYPE_DELIMITED = {"txt_delimited", "csv"}
FILE_TYPE_XLSX = {"xlsx"}


FILE_TYPE_JSON = {"json"}
FILE_TYPE_XML = {"xml"}


def get_step4_variant(file_type_code: str) -> str:
    code = (file_type_code or "").strip()
    if code in FILE_TYPE_FIXED:
        return "fixed"
    if code in FILE_TYPE_DELIMITED:
        return "delimited"
    if code in FILE_TYPE_XLSX:
        return "xlsx"
    if code in FILE_TYPE_JSON:
        return "json"
    if code in FILE_TYPE_XML:
        return "xml"
    return "unsupported"


def default_config_for_type(file_type_code: str, current: dict | None = None) -> dict:
    base = dict(current or {})
    variant = get_step4_variant(file_type_code)
    if variant == "delimited":
        for key, value in DEFAULT_DELIMITED_CONFIG.items():
            base.setdefault(key, value)
    elif variant == "xlsx":
        for key, value in DEFAULT_XLSX_CONFIG.items():
            base.setdefault(key, value)
    elif variant == "json":
        for key, value in DEFAULT_JSON_CONFIG.items():
            base.setdefault(key, value)
    elif variant == "xml":
        for key, value in DEFAULT_XML_CONFIG.items():
            base.setdefault(key, value)
    return base


def default_fields_for_type(file_type_code: str) -> list:
    variant = get_step4_variant(file_type_code)
    if variant == "fixed":
        return copy.deepcopy(DEFAULT_POSITIONAL_FIELDS)
    if variant == "delimited":
        return copy.deepcopy(DEFAULT_DELIMITED_FIELDS)
    if variant == "xlsx":
        return copy.deepcopy(DEFAULT_XLSX_FIELDS)
    if variant == "json":
        return copy.deepcopy(DEFAULT_JSON_FIELDS)
    if variant == "xml":
        return copy.deepcopy(DEFAULT_XML_FIELDS)
    return []


def fields_match_variant(fields: list, variant: str) -> bool:
    if not fields:
        return False
    if variant == "fixed":
        return all("start" in item and "end" in item for item in fields)
    if variant == "delimited":
        return all("column_index" in item for item in fields)
    if variant == "xlsx":
        return all("column" in item for item in fields)
    if variant == "json":
        return all("json_path" in item for item in fields)
    if variant == "xml":
        return all("element" in item for item in fields)
    return False


def _capture_start_summary(capture: dict) -> str:
    mode = capture.get("mode", "—")
    if mode == "line_number":
        return f"Modo line_number · línea {capture.get('line', 1)}"
    if mode == "first":
        return "Modo first · línea 1"
    if mode == "eof":
        return "Modo eof"
    if mode == "after_header_block":
        return f"Modo after_header_block · skip {capture.get('skip_lines', 0)}"
    if mode == "marker_start":
        return f"Marcador «{capture.get('marker', '')}»"
    if mode == "after_pattern":
        return f"Patrón inicio · {capture.get('pattern', '—')}"
    if mode == "after_blank_run":
        return f"Tras {capture.get('blank_count', 1)} línea(s) en blanco"
    return f"Modo {mode}"


def _capture_end_summary(capture: dict) -> str:
    mode = capture.get("mode", "—")
    if mode == "eof":
        return "Modo eof — final del archivo"
    if mode == "line_number":
        return f"Modo line_number · línea {capture.get('line', '—')}"
    if mode == "percent":
        return f"Modo percent · {capture.get('value', '—')}%"
    if mode == "max_rows":
        return f"Modo max_rows · {capture.get('max_rows', '—')}"
    if mode == "before_pattern":
        return f"Patrón fin · {capture.get('pattern', '—')}"
    if mode == "marker_end":
        return f"Marcador fin «{capture.get('marker', '')}»"
    if mode == "blank_run":
        return f"Hasta {capture.get('blank_count', 1)} línea(s) en blanco"
    if mode == "line_or_eof":
        return f"Línea {capture.get('line', '—')} o EOF"
    return f"Modo {mode}"


def _fields_summary(fields: list) -> str:
    if not fields:
        return "Sin campos definidos"
    names = [item.get("name", "?") for item in fields[:4]]
    suffix = "…" if len(fields) > 4 else ""
    return ", ".join(names) + suffix


def _rules_summary(rules: dict) -> str:
    parts = []
    if rules.get("trim_lines"):
        parts.append("trim_lines")
    if rules.get("skip_empty_lines"):
        parts.append("skip_empty_lines")
    if rules.get("comment_prefix"):
        parts.append(f"comment_prefix={rules['comment_prefix']}")
    return ", ".join(parts) if parts else "Sin reglas"


def _report_summary(report: dict) -> str:
    if not report.get("report_enabled"):
        return "Informe deshabilitado"
    parts = []
    if report.get("include_summary"):
        parts.append("resumen")
    if report.get("include_row_errors"):
        parts.append("detalle filas")
    fmt = report.get("report_format", "json")
    return f"{', '.join(parts)} · {fmt}" if parts else f"formato {fmt}"


def get_wizard_context(project, membership=None) -> SourceWizardContext:
    source = source_persistence_service.get_source_dict(project)
    version = source_persistence_service.get_draft_version(project)
    role = membership.role if membership else "—"
    statuses = source_persistence_service.step_statuses(source)

    steps = [
        WizardStepStatus(
            1,
            "paso-1",
            "Paso 1 — Tipo de archivo",
            source_persistence_service.file_type_label(source.get("file_type_code", "")),
            statuses[0],
            "dms:source_step1",
        ),
        WizardStepStatus(
            2,
            "paso-2",
            "Paso 2 — Línea de inicio",
            _capture_start_summary(source.get("capture_start") or {}),
            statuses[1],
            "dms:source_step2",
        ),
        WizardStepStatus(
            3,
            "paso-3",
            "Paso 3 — Línea de fin",
            _capture_end_summary(source.get("capture_end") or {}),
            statuses[2],
            "dms:source_step3",
        ),
        WizardStepStatus(
            4,
            "paso-4",
            "Paso 4 — Campos / columnas",
            _fields_summary(source.get("fields") or []),
            statuses[3],
            "dms:source_step4",
        ),
        WizardStepStatus(
            5,
            "paso-5",
            "Paso 5 — Reglas globales",
            _rules_summary(source.get("content_rules") or {}),
            statuses[4],
            "dms:source_step5",
        ),
        WizardStepStatus(
            6,
            "paso-6",
            "Paso 6 — Informe de procesamiento",
            _report_summary(source.get("processing_report") or {}),
            statuses[5],
            "dms:source_step6",
        ),
    ]
    done = sum(1 for step in steps if step.status == "done")
    fields = source.get("fields") or []
    continue_url = "dms:source_step1"
    for step in steps:
        if step.status != "done":
            continue_url = step.url_name
            break
    return SourceWizardContext(
        project_name=project.name,
        project_slug=project.slug,
        membership_role=role,
        version_label=f"Borrador v{version.version_number}",
        version_number=version.version_number,
        steps_complete=done,
        steps_total=6,
        file_type_label=source_persistence_service.file_type_label(source.get("file_type_code", "")),
        fields_count=len(fields),
        steps=steps,
        continue_step_url_name=continue_url,
    )


def get_content_type_choices():
    qs = FieldContentType.objects.filter(is_active=True).order_by("sort_order", "code")
    if qs.exists():
        return [{"code": item.code, "name": item.name} for item in qs]
    return [
        {"code": "numeric", "name": "Solo números"},
        {"code": "alpha", "name": "Solo letras"},
        {"code": "alphanumeric", "name": "Alfanumérico"},
        {"code": "decimal", "name": "Decimal"},
        {"code": "alphanumeric_spaces", "name": "Alfanumérico con espacios"},
        {"code": "date", "name": "Fecha"},
        {"code": "datetime", "name": "Fecha y hora"},
        {"code": "free_text", "name": "Texto libre"},
        {"code": "custom", "name": "Patrón propio"},
    ]


def source_context(project) -> dict:
    source = source_persistence_service.get_source_dict(project)
    return {
        "source": source,
        "source_json": json.dumps(source),
        "can_edit_source": True,
    }


def get_step4_context(project, variant: str | None = None) -> dict:
    source = source_persistence_service.ensure_step4_coherence(project)
    file_type = source.get("file_type_code", "")
    resolved = variant or get_step4_variant(file_type)
    fields = source.get("fields") or default_fields_for_type(file_type)
    config = default_config_for_type(file_type, source.get("config") or {})
    return {
        "step4_variant": resolved,
        "file_type_code": file_type,
        "fields_json": json.dumps(fields),
        "fields_count": len(fields),
        "config_json": json.dumps(config),
        "content_types": get_content_type_choices(),
    }


def get_step4_positional_context(project) -> dict:
    return get_step4_context(project, "fixed")


def get_step5_content_rules_context(project) -> dict:
    source = source_persistence_service.get_source_dict(project)
    rules = source.get("content_rules") or DEFAULT_CONTENT_RULES
    return {
        "content_rules_json": json.dumps(rules),
    }


def get_step6_report_context(project) -> dict:
    source = source_persistence_service.get_source_dict(project)
    report = source.get("processing_report") or DEFAULT_PROCESSING_REPORT
    return {
        "processing_report_json": json.dumps(report),
    }
