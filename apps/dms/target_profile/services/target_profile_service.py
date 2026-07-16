"""Servicios del asistente TargetProfile (target_definition.md)."""

import copy
import json
from dataclasses import dataclass, field

from apps.dms.target_profile.services import target_persistence_service
from apps.dms.target_profile.services.target_profile_catalog_service import get_data_types

DEFAULT_SERIALIZATION = {
    "trim_before_write": True,
    "default_truncate": "right",
    "date_format": "YYYY-MM-DD",
    "boolean_format": "1_0",
    "null_representation": "",
    "decimal_places": 2,
    "decimal_separator": ".",
}

DEFAULT_WRITE_VALIDATION = {
    "policy": "reject_row",
    "on_type_mismatch": "reject_row",
    "on_length_exceeded": "truncate",
    "on_required_empty": "reject_row",
}

DEFAULT_LAYOUT_CSV = {
    "delimiter": ",",
    "quote_char": '"',
    "escape_char": "\\",
    "include_header": True,
    "include_bom": False,
    "output_filename_pattern": "salida_{date:%Y%m%d}.csv",
}

DEFAULT_LAYOUT_FIXED = {
    "record_length": None,
    "trailing_newline": True,
    "include_bom": False,
    "output_filename_pattern": "salida_{date:%Y%m%d}.txt",
}

DEFAULT_LAYOUT_XLSX = {
    "sheet_name": "Hoja1",
    "include_header": True,
    "freeze_header_row": True,
    "column_width_auto": True,
    "output_filename_pattern": "salida_{date:%Y%m%d}.xlsx",
}

DEFAULT_LAYOUT_JSON = {
    "root_type": "array",
    "records_path": "",
    "pretty_print": True,
    "indent": 2,
    "output_filename_pattern": "salida_{date:%Y%m%d}.json",
}

DEFAULT_LAYOUT_XML = {
    "root_element": "records",
    "record_element": "record",
    "namespace": "",
    "declaration": True,
    "output_filename_pattern": "salida_{date:%Y%m%d}.xml",
}

DEFAULT_DELIMITED_FIELDS = [
    {"name": "documento", "label": "documento", "order": 1, "data_type": "string", "required": True},
    {"name": "nombre", "label": "nombre", "order": 2, "data_type": "string", "required": True},
    {"name": "salario", "label": "salario", "order": 3, "data_type": "integer", "required": True},
    {"name": "estado", "label": "estado", "order": 4, "data_type": "string", "required": False},
]

DEFAULT_FIXED_FIELDS = [
    {
        "name": "documento",
        "label": "documento",
        "order": 1,
        "data_type": "string",
        "required": True,
        "start": 1,
        "end": 5,
        "align": "right",
        "pad_char": "0",
        "max_length": 5,
    },
    {
        "name": "nombre",
        "label": "nombre",
        "order": 2,
        "data_type": "string",
        "required": True,
        "start": 6,
        "end": 15,
        "align": "left",
        "pad_char": " ",
        "max_length": 10,
    },
    {
        "name": "salario",
        "label": "salario",
        "order": 3,
        "data_type": "integer",
        "required": True,
        "start": 16,
        "end": 21,
        "align": "right",
        "pad_char": "0",
        "max_length": 6,
    },
]

DEFAULT_XLSX_FIELDS = [
    {
        "name": "documento",
        "label": "documento",
        "order": 1,
        "column": "A",
        "excel_type": "text",
        "data_type": "string",
        "required": True,
    },
    {
        "name": "nombre",
        "label": "nombre",
        "order": 2,
        "column": "B",
        "excel_type": "text",
        "data_type": "string",
        "required": True,
    },
    {
        "name": "salario",
        "label": "salario",
        "order": 3,
        "column": "C",
        "excel_type": "number",
        "data_type": "integer",
        "required": True,
    },
]

DEFAULT_JSON_FIELDS = [
    {
        "name": "documento",
        "label": "documento",
        "order": 1,
        "path": "documento",
        "data_type": "string",
        "required": True,
    },
    {
        "name": "nombre",
        "label": "nombre",
        "order": 2,
        "path": "nombre",
        "data_type": "string",
        "required": True,
    },
    {
        "name": "salario",
        "label": "salario",
        "order": 3,
        "path": "salario",
        "data_type": "integer",
        "required": True,
    },
]

DEFAULT_XML_FIELDS = [
    {
        "name": "documento",
        "label": "documento",
        "order": 1,
        "path": "documento",
        "data_type": "string",
        "required": True,
    },
    {
        "name": "nombre",
        "label": "nombre",
        "order": 2,
        "path": "nombre",
        "data_type": "string",
        "required": True,
    },
    {
        "name": "salario",
        "label": "salario",
        "order": 3,
        "path": "salario",
        "data_type": "integer",
        "required": True,
    },
]

FILE_TYPE_FIXED = {"txt_fixed"}
FILE_TYPE_DELIMITED = {"txt_delimited", "csv"}
FILE_TYPE_XLSX = {"xlsx"}
FILE_TYPE_JSON = {"json"}
FILE_TYPE_XML = {"xml"}


@dataclass
class WizardStepStatus:
    number: int
    slug: str
    title: str
    summary: str
    status: str
    url_name: str


@dataclass
class TargetWizardContext:
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
    continue_step_url_name: str = "dms:target_step1"


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


def default_layout_for_type(file_type_code: str, preserved: dict | None = None) -> dict:
    code = (file_type_code or "").strip()
    base = copy.deepcopy(preserved or {})
    if code in FILE_TYPE_FIXED:
        layout = copy.deepcopy(DEFAULT_LAYOUT_FIXED)
    elif code in FILE_TYPE_XLSX:
        layout = copy.deepcopy(DEFAULT_LAYOUT_XLSX)
    elif code in FILE_TYPE_JSON:
        layout = copy.deepcopy(DEFAULT_LAYOUT_JSON)
    elif code in FILE_TYPE_XML:
        layout = copy.deepcopy(DEFAULT_LAYOUT_XML)
    else:
        layout = copy.deepcopy(DEFAULT_LAYOUT_CSV)
        if code == "txt_delimited":
            layout["delimiter"] = ";"
            layout["output_filename_pattern"] = "salida_{date:%Y%m%d}.txt"
    pattern = base.get("output_filename_pattern")
    if pattern:
        layout["output_filename_pattern"] = pattern
    if "include_bom" in base and code not in FILE_TYPE_XLSX | FILE_TYPE_XML:
        layout["include_bom"] = base["include_bom"]
    return layout


def default_fields_for_type(file_type_code: str) -> list:
    code = (file_type_code or "").strip()
    if code in FILE_TYPE_FIXED:
        return copy.deepcopy(DEFAULT_FIXED_FIELDS)
    if code in FILE_TYPE_XLSX:
        return copy.deepcopy(DEFAULT_XLSX_FIELDS)
    if code in FILE_TYPE_JSON:
        return copy.deepcopy(DEFAULT_JSON_FIELDS)
    if code in FILE_TYPE_XML:
        return copy.deepcopy(DEFAULT_XML_FIELDS)
    return copy.deepcopy(DEFAULT_DELIMITED_FIELDS)


def _layout_summary(target: dict) -> str:
    layout = target.get("layout") or {}
    code = target.get("file_type_code") or ""
    if code in FILE_TYPE_DELIMITED:
        delim = layout.get("delimiter") or "—"
        header = "con encabezado" if layout.get("include_header") else "sin encabezado"
        return f"Delimitador «{delim}» · {header}"
    if code in FILE_TYPE_XLSX:
        return f"Hoja «{layout.get('sheet_name') or '—'}»"
    if code in FILE_TYPE_FIXED:
        length = layout.get("record_length")
        return f"Longitud registro: {length}" if length else "Posicional"
    if code in FILE_TYPE_JSON:
        root = layout.get("root_type") or "array"
        return f"JSON · raíz {root}"
    if code in FILE_TYPE_XML:
        return (
            f"XML · <{layout.get('root_element') or '—'}> / "
            f"<{layout.get('record_element') or '—'}>"
        )
    return "Layout pendiente"

def get_wizard_context(project, membership) -> TargetWizardContext:
    target = target_persistence_service.get_target_dict(project)
    version = target_persistence_service.get_or_create_draft_with_target(project)
    statuses = target_persistence_service.step_statuses(target)
    role = membership.role if membership else "—"

    step_defs = [
        (1, "tipo", "Tipo de salida", target_persistence_service.file_type_label(target.get("file_type_code", "")), "dms:target_step1"),
        (2, "encoding", "Codificación", f"{target.get('encoding_code') or '—'} / {target.get('line_ending_code') or '—'}", "dms:target_step2"),
        (3, "layout", "Layout", _layout_summary(target), "dms:target_step3"),
        (4, "campos", "Campos destino", f"{len(target.get('fields') or [])} campos", "dms:target_step4"),
        (5, "serializacion", "Serialización", "Reglas de formato al escribir", "dms:target_step5"),
        (6, "validacion", "Validación escritura", (target.get("write_validation") or {}).get("policy") or "Pendiente", "dms:target_step6"),
    ]

    steps = []
    continue_url = "dms:target_step1"
    complete = 0
    for (number, slug, title, summary, url_name), status in zip(step_defs, statuses):
        if status == "done":
            complete += 1
        steps.append(
            WizardStepStatus(
                number=number,
                slug=slug,
                title=title,
                summary=summary,
                status=status,
                url_name=url_name,
            )
        )
    for step in steps:
        if step.status != "done":
            continue_url = step.url_name
            break
    # Si todo está completo, llevar a revisar desde el paso 1 (no recargar el hub).
    if complete == 6:
        continue_url = "dms:target_step1"

    return TargetWizardContext(
        project_name=project.name,
        project_slug=project.slug,
        membership_role=role,
        version_label=f"Borrador v{version.version_number}",
        version_number=version.version_number,
        steps_complete=complete,
        file_type_label=target_persistence_service.file_type_label(target.get("file_type_code", "")),
        fields_count=len(target.get("fields") or []),
        steps=steps,
        continue_step_url_name=continue_url,
    )


def target_context(project) -> dict:
    target = target_persistence_service.get_target_dict(project)
    return {"target": target, "target_json": json.dumps(target)}


def get_step4_context(project, variant: str) -> dict:
    target = target_persistence_service.get_target_dict(project)
    return {
        "file_type_code": target.get("file_type_code") or "",
        "data_types": get_data_types(),
        "variant": variant,
        "layout": target.get("layout") or {},
    }


def get_step3_context(project) -> dict:
    target = target_persistence_service.get_target_dict(project)
    code = target.get("file_type_code") or ""
    return {
        "file_type_code": code,
        "layout_variant": get_step4_variant(code),
        "layout": target.get("layout") or {},
    }


def get_step5_context(project) -> dict:
    target = target_persistence_service.get_target_dict(project)
    return {"serialization": target.get("serialization") or copy.deepcopy(DEFAULT_SERIALIZATION)}


def get_step6_context(project) -> dict:
    target = target_persistence_service.get_target_dict(project)
    return {
        "write_validation": target.get("write_validation")
        or copy.deepcopy(DEFAULT_WRITE_VALIDATION),
        "policies": [
            ("reject_row", "Rechazar fila"),
            ("abort", "Abortar job"),
            ("truncate", "Truncar y escribir"),
            ("use_default", "Usar valor por defecto"),
            ("write_empty", "Escribir vacío"),
        ],
    }
