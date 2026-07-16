"""Importar campos de SourceProfile hacia TargetProfile (punto de partida editable)."""

from __future__ import annotations

import copy
import logging
import re

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.services import (
    field_normalization_service,
    target_persistence_service,
    target_profile_service,
)

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

CONTENT_TYPE_TO_DATA_TYPE = {
    "numeric": "integer",
    "decimal": "decimal",
    "date": "date",
    "datetime": "datetime",
    "alpha": "string",
    "alphanumeric": "string",
    "alphanumeric_spaces": "string",
    "free_text": "string",
    "custom": "string",
}

DATA_TYPE_TO_EXCEL = {
    "integer": "number",
    "decimal": "number",
    "float": "number",
    "date": "date",
    "datetime": "date",
    "boolean": "boolean",
}


def _slug_name(raw: str, fallback: str) -> str:
    name = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)
    if not name or not _NAME_RE.match(name):
        name = fallback
    return name


def _map_data_type(source_field: dict) -> str:
    if source_field.get("data_type"):
        return str(source_field["data_type"]).strip() or "string"
    content = (source_field.get("content_type") or "").strip().lower()
    return CONTENT_TYPE_TO_DATA_TYPE.get(content, "string")


def _excel_column(index_1based: int) -> str:
    n = max(1, index_1based)
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _source_order(field: dict, index_1based: int) -> int:
    for key in ("order", "column_index"):
        raw = field.get(key)
        if raw not in (None, ""):
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                pass
    return index_1based


def _build_fixed_field(source_field: dict, order: int, cursor: list[int]) -> dict:
    """cursor[0] = next free start position (1-based)."""
    start = source_field.get("start")
    end = source_field.get("end")
    length = source_field.get("length")
    try:
        start = int(start) if start not in (None, "") else None
    except (TypeError, ValueError):
        start = None
    try:
        end = int(end) if end not in (None, "") else None
    except (TypeError, ValueError):
        end = None
    try:
        length = int(length) if length not in (None, "") else None
    except (TypeError, ValueError):
        length = None

    if start is None:
        start = cursor[0]
    if end is None:
        if length is not None and length >= 1:
            end = start + length - 1
        else:
            end = start
    if end < start:
        end = start
    length = end - start + 1
    cursor[0] = max(cursor[0], end + 1)

    return {
        "name": source_field["name"],
        "label": source_field["label"],
        "order": order,
        "data_type": source_field["data_type"],
        "required": source_field["required"],
        "start": start,
        "end": end,
        "length": length,
        "align": "left",
        "pad_char": " ",
        "max_length": length,
    }


def _build_delimited_field(source_field: dict, order: int) -> dict:
    return {
        "name": source_field["name"],
        "label": source_field["label"],
        "order": order,
        "data_type": source_field["data_type"],
        "required": source_field["required"],
    }


def _build_xlsx_field(source_field: dict, order: int, index_1based: int) -> dict:
    column = (source_field.get("column") or "").strip().upper()
    if not column:
        col_idx = source_field.get("column_index")
        try:
            column = _excel_column(int(col_idx)) if col_idx not in (None, "") else _excel_column(index_1based)
        except (TypeError, ValueError):
            column = _excel_column(index_1based)
    data_type = source_field["data_type"]
    return {
        "name": source_field["name"],
        "label": source_field["label"],
        "order": order,
        "column": column,
        "excel_type": DATA_TYPE_TO_EXCEL.get(data_type, "text"),
        "data_type": data_type,
        "required": source_field["required"],
    }


def _build_path_field(source_field: dict, order: int) -> dict:
    path = (
        (source_field.get("path") or "").strip()
        or (source_field.get("json_path") or "").strip()
        or (source_field.get("element") or "").strip()
        or source_field["name"]
    )
    return {
        "name": source_field["name"],
        "label": source_field["label"],
        "order": order,
        "path": path,
        "data_type": source_field["data_type"],
        "required": source_field["required"],
    }


def build_fields_from_source(project) -> OperationResult:
    """Convierte campos de origen al shape del tipo destino actual (sin persistir)."""
    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)

    source_fields = source.get("fields") or []
    if not source_fields:
        return OperationResult.failure(
            "validation_form",
            "Defina primero los campos en el perfil de origen.",
            errors={"fields": ["El origen no tiene campos definidos."]},
        )

    target_type = (target.get("file_type_code") or "").strip()
    if not target_type:
        return OperationResult.failure(
            "validation_form",
            "Seleccione el tipo de archivo destino (paso 1) antes de importar campos.",
            errors={"file_type_code": ["Tipo de destino pendiente."]},
        )

    variant = target_profile_service.get_step4_variant(target_type)
    if variant == "unsupported":
        return OperationResult.failure(
            "validation_form",
            "El tipo de archivo destino no admite editor de campos.",
            errors={"file_type_code": ["Tipo no soportado."]},
        )

    source_type = (source.get("file_type_code") or "").strip()
    warnings: list[str] = []
    if source_type and source_type != target_type:
        warnings.append(
            f"Origen «{source_type}» y destino «{target_type}» difieren; "
            "la estructura se adaptó al tipo de salida."
        )

    prepared: list[dict] = []
    used_names: set[str] = set()
    cursor = [1]

    for index, raw in enumerate(source_fields, start=1):
        item = dict(raw or {})
        fallback = f"campo_{index}"
        name = _slug_name(item.get("name") or "", fallback)
        if name in used_names:
            name = f"{name}_{index}"
        used_names.add(name)
        label = (item.get("label") or "").strip() or name
        base = {
            "name": name,
            "label": label,
            "data_type": _map_data_type(item),
            "required": bool(item.get("required")),
        }
        order = _source_order(item, index)
        if variant == "fixed":
            prepared.append(_build_fixed_field({**item, **base}, order, cursor))
        elif variant == "delimited":
            prepared.append(_build_delimited_field({**base}, order))
        elif variant in {"json", "xml"}:
            prepared.append(_build_path_field({**item, **base}, order))
        else:
            prepared.append(_build_xlsx_field({**item, **base}, order, index))

    prepared.sort(key=lambda f: (f.get("order") or 0, f.get("name") or ""))
    for i, field in enumerate(prepared, start=1):
        field["order"] = i

    normalized = field_normalization_service.normalize_fields_list(prepared, target_type)
    return OperationResult.success(
        user_message=f"Se prepararon {len(normalized)} campos desde el origen.",
        payload={
            "fields": normalized,
            "source_fields_count": len(source_fields),
            "target_file_type": target_type,
            "source_file_type": source_type,
            "variant": variant,
            "warnings": warnings,
        },
    )


def import_and_save_fields_from_source(user, project) -> OperationResult:
    """Importa desde origen y persiste reemplazando fields destino."""
    if not target_persistence_service.user_can_edit_target(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar la definición de destino.",
        )

    built = build_fields_from_source(project)
    if not built.ok:
        return built

    fields = copy.deepcopy(built.payload["fields"])
    saved = target_persistence_service.save_target(
        user,
        project,
        {"fields": fields},
        strict=False,
    )
    if not saved.ok:
        return saved

    warnings = list(built.payload.get("warnings") or [])
    warning_messages = list(saved.payload.get("warning_messages") or [])
    return OperationResult.success(
        user_message=(
            f"Se importaron {len(fields)} campos desde el origen. "
            "Puede editarlos o eliminarlos antes de continuar."
        ),
        payload={
            "fields": fields,
            "target": saved.payload.get("target"),
            "warnings": warnings,
            "warning_messages": warning_messages + warnings,
            "source_fields_count": built.payload.get("source_fields_count"),
            "variant": built.payload.get("variant"),
        },
    )
