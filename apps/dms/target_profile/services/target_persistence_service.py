"""Persistencia de DmsTargetProfile sobre borrador DmsMappingVersion."""

import copy
import logging

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.models import DmsTargetProfile
from apps.projects.models import Project

logger = logging.getLogger(__name__)

FILE_TYPE_LABELS = {
    "txt_fixed": "TXT posicional",
    "txt_delimited": "TXT delimitado",
    "csv": "CSV",
    "xlsx": "Excel",
    "json": "JSON",
    "xml": "XML",
}

WRITE_POLICIES = frozenset(
    {"reject_row", "abort", "truncate", "use_default", "write_empty"}
)


def default_target_dict() -> dict:
    """Perfil vacío para borradores nuevos (sin datos de ejemplo precargados)."""
    return {
        "file_type_code": "",
        "encoding_code": None,
        "encoding_custom": None,
        "line_ending_code": None,
        "line_ending_custom": None,
        "layout": {},
        "fields": [],
        "serialization": {},
        "write_validation": {},
        "config": {},
    }


def user_can_edit_target(user, project: Project) -> bool:
    return source_persistence_service.user_can_edit_source(user, project)


def profile_to_dict(profile: DmsTargetProfile) -> dict:
    from apps.dms.target_profile.services.field_normalization_service import flatten_field_for_edit

    fields = [flatten_field_for_edit(item) for item in (profile.fields or [])]
    config = profile.config or {}
    return {
        "file_type_code": profile.file_type_code,
        "encoding_code": config.get("encoding_code") or "",
        "encoding_custom": config.get("encoding_custom"),
        "line_ending_code": config.get("line_ending_code") or "",
        "line_ending_custom": config.get("line_ending_custom"),
        "layout": profile.layout or {},
        "fields": fields,
        "serialization": profile.serialization or {},
        "write_validation": profile.write_validation or {},
        "config": config,
    }


def _apply_config_fields(data: dict, profile: DmsTargetProfile) -> None:
    config = dict(profile.config or {})
    for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
        if key in data:
            value = data[key]
            if value is None or value == "":
                config.pop(key, None)
            else:
                config[key] = value
    profile.config = config


def apply_dict_to_profile(profile: DmsTargetProfile, data: dict) -> None:
    if "file_type_code" in data:
        profile.file_type_code = (data.get("file_type_code") or "").strip()
    if "layout" in data:
        profile.layout = data["layout"] or {}
    if "serialization" in data:
        profile.serialization = data["serialization"] or {}
    if "write_validation" in data:
        profile.write_validation = data["write_validation"] or {}
    if "fields" in data:
        profile.fields = data["fields"] or []
    if "config" in data:
        profile.config = data["config"] or {}
    _apply_config_fields(data, profile)


def flatten_validation_messages(bucket: dict[str, list[str]] | None) -> list[str]:
    messages: list[str] = []
    for items in (bucket or {}).values():
        messages.extend(items)
    return messages


def validate_target_dict(
    data: dict,
    *,
    strict: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    file_type = (data.get("file_type_code") or "").strip()
    if strict and not file_type:
        errors.setdefault("file_type_code", []).append("Seleccione un tipo de archivo de salida.")

    if strict and not (data.get("encoding_code") or "").strip():
        errors.setdefault("encoding_code", []).append("Seleccione la codificación de salida.")
    if strict and file_type in ("txt_fixed", "txt_delimited", "csv") and not (
        data.get("line_ending_code") or ""
    ).strip():
        errors.setdefault("line_ending_code", []).append("Seleccione el final de línea de salida.")

    fields = data.get("fields") or []
    if strict and not fields:
        errors.setdefault("fields", []).append("Defina al menos un campo destino.")

    names: set[str] = set()
    orders: set[int] = set()
    for field in fields:
        name = (field.get("name") or "").strip().lower()
        if not name:
            errors.setdefault("fields", []).append("Hay campos destino sin nombre.")
            continue
        if name in names:
            errors.setdefault("fields", []).append(f"Nombre de campo duplicado: «{name}».")
        names.add(name)

        try:
            order = int(field.get("order"))
        except (TypeError, ValueError):
            errors.setdefault("fields", []).append(f"Campo «{name}»: order inválido.")
            order = None
        if order is not None:
            if order in orders:
                errors.setdefault("fields", []).append(f"Orden duplicado: {order}.")
            orders.add(order)

        data_type = (field.get("data_type") or "").strip()
        if not data_type and strict:
            errors.setdefault("fields", []).append(f"Campo «{name}»: indique data_type.")
        if data_type == "date" and not (field.get("date_format") or "").strip():
            warnings.setdefault("fields", []).append(
                f"Campo «{name}»: se recomienda indicar date_format."
            )
        if data_type == "datetime" and not (
            (field.get("datetime_format") or field.get("date_format") or "").strip()
        ):
            warnings.setdefault("fields", []).append(
                f"Campo «{name}»: se recomienda indicar datetime_format."
            )

    layout = data.get("layout") or {}
    if file_type == "txt_fixed":
        from apps.dms.target_profile.services.field_normalization_service import (
            flatten_field_for_edit,
        )

        positional = []
        for field in fields:
            item = flatten_field_for_edit(field)
            name = item.get("name", "?")
            try:
                start = int(item.get("start"))
                end = int(item.get("end"))
            except (TypeError, ValueError):
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: inicio y fin deben ser números."
                )
                continue
            if end < start:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: el fin debe ser ≥ al inicio."
                )
            if strict and item.get("max_length") in (None, ""):
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: max_length es obligatorio en txt_fixed."
                )
            positional.append((start, end, name))

        positional.sort()
        for index in range(1, len(positional)):
            prev_start, prev_end, prev_name = positional[index - 1]
            start, end, name = positional[index]
            if start <= prev_end:
                errors.setdefault("fields", []).append(
                    f"Solapamiento entre «{prev_name}» ({prev_start}-{prev_end}) "
                    f"y «{name}» ({start}-{end})."
                )

        record_length = layout.get("record_length")
        if record_length not in (None, ""):
            try:
                record_length = int(record_length)
            except (TypeError, ValueError):
                errors.setdefault("layout", []).append("record_length inválido.")
                record_length = None
            if record_length is not None and positional:
                max_end = max(item[1] for item in positional)
                if max_end > record_length:
                    errors.setdefault("layout", []).append(
                        f"Los campos superan record_length ({max_end} > {record_length})."
                    )

    if file_type in ("txt_delimited", "csv"):
        if strict and not (layout.get("delimiter") or "").strip():
            errors.setdefault("layout", []).append("Indique el delimitador del archivo.")
        if strict and "include_header" not in layout:
            errors.setdefault("layout", []).append("Indique si incluye encabezado.")

    if file_type == "xlsx":
        if strict and not (layout.get("sheet_name") or "").strip():
            errors.setdefault("layout", []).append("Indique el nombre de la hoja Excel.")
        columns: set[str] = set()
        for field in fields:
            column = (field.get("column") or "").strip().upper()
            name = field.get("name", "?")
            if not column:
                errors.setdefault("fields", []).append(f"Campo «{name}»: indique la columna.")
                continue
            if column in columns:
                errors.setdefault("fields", []).append(f"Columna duplicada: {column}.")
            columns.add(column)

    if file_type == "json":
        root_type = (layout.get("root_type") or "").strip()
        if strict and root_type not in {"array", "object"}:
            errors.setdefault("layout", []).append(
                "Indique el tipo de raíz JSON (array u object)."
            )
        paths: set[str] = set()
        for field in fields:
            name = field.get("name", "?")
            path = (field.get("path") or name).strip()
            if strict and not path:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: indique la ruta JSON (path)."
                )
            if path in paths:
                errors.setdefault("fields", []).append(f"Ruta JSON duplicada: {path}.")
            paths.add(path)

    if file_type == "xml":
        if strict and not (layout.get("root_element") or "").strip():
            errors.setdefault("layout", []).append("Indique el elemento raíz XML.")
        if strict and not (layout.get("record_element") or "").strip():
            errors.setdefault("layout", []).append("Indique el elemento de registro XML.")
        paths: set[str] = set()
        for field in fields:
            name = field.get("name", "?")
            path = (field.get("path") or name).strip()
            if strict and not path:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: indique el elemento hijo (path)."
                )
            if path in paths:
                errors.setdefault("fields", []).append(f"Elemento XML duplicado: {path}.")
            paths.add(path)

    write_validation = data.get("write_validation") or {}
    if strict and not (write_validation.get("policy") or "").strip():
        errors.setdefault("write_validation", []).append(
            "Defina la política de validación al escribir."
        )
    for key in ("policy", "on_type_mismatch", "on_length_exceeded", "on_required_empty"):
        value = (write_validation.get(key) or "").strip()
        if value and value not in WRITE_POLICIES:
            errors.setdefault("write_validation", []).append(
                f"Política «{key}» no válida: {value}."
            )

    return errors, warnings


def profile_defaults_from_dict(data: dict) -> dict:
    config = dict(data.get("config") or {})
    for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
        if key in data and data[key] is not None:
            config[key] = data[key]
    return {
        "file_type_code": data.get("file_type_code", ""),
        "layout": data.get("layout") or {},
        "serialization": data.get("serialization") or {},
        "write_validation": data.get("write_validation") or {},
        "fields": data.get("fields") or [],
        "config": config,
    }


def ensure_target_on_version(version: DmsMappingVersion) -> DmsTargetProfile:
    profile, _created = DmsTargetProfile.objects.get_or_create(
        version=version,
        defaults=profile_defaults_from_dict(default_target_dict()),
    )
    return profile


def get_or_create_draft_with_target(project: Project) -> DmsMappingVersion:
    version = source_persistence_service.get_or_create_draft_version(project)
    ensure_target_on_version(version)
    return version


def get_target_dict(project: Project) -> dict:
    version = get_or_create_draft_with_target(project)
    return profile_to_dict(version.target_profile)


def merge_target_dict(current: dict, partial: dict) -> dict:
    merged = copy.deepcopy(current)
    replace_keys = {"layout", "serialization", "write_validation"}
    merge_keys = {"config"}
    for key, value in partial.items():
        if key in replace_keys:
            merged[key] = copy.deepcopy(value) if isinstance(value, dict) else value
        elif key in merge_keys:
            if isinstance(value, dict):
                base = merged.get(key) or {}
                merged[key] = {**base, **value}
            else:
                merged[key] = value
        else:
            merged[key] = value
    return merged


@transaction.atomic
def save_target(
    user,
    project: Project,
    partial: dict,
    *,
    strict: bool = False,
) -> OperationResult:
    if not user_can_edit_target(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar la definición de destino.",
        )

    version = get_or_create_draft_with_target(project)
    profile = version.target_profile
    current = profile_to_dict(profile)
    merged = merge_target_dict(current, partial)

    new_type = (merged.get("file_type_code") or "").strip()
    old_type = (current.get("file_type_code") or "").strip()
    new_type = (merged.get("file_type_code") or "").strip()
    old_type = (current.get("file_type_code") or "").strip()
    if new_type and new_type != old_type:
        # Campos y layout se definen en pasos posteriores; no precargar demo.
        merged["fields"] = []
        if "layout" not in partial:
            merged["layout"] = {}
        preserved = {
            k: merged.get(k) or current.get(k)
            for k in (
                "encoding_code",
                "encoding_custom",
                "line_ending_code",
                "line_ending_custom",
            )
            if merged.get(k) or current.get(k)
        }
        for key, value in preserved.items():
            if value:
                merged[key] = value

    from apps.dms.target_profile.services.field_normalization_service import normalize_fields_list

    merged["fields"] = normalize_fields_list(
        merged.get("fields") or [],
        merged.get("file_type_code") or "",
    )

    errors, warnings = validate_target_dict(merged, strict=strict)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del perfil de destino.",
            errors=errors,
            warnings=warnings,
        )

    try:
        apply_dict_to_profile(profile, merged)
        profile.save()
        version.save(update_fields=["updated_at"])
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("save_target unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Perfil de destino guardado correctamente.",
        payload={
            "target": profile_to_dict(profile),
            "version": version,
            "warnings": warnings,
            "warning_messages": flatten_validation_messages(warnings),
        },
    )


def file_type_label(code: str) -> str:
    if not code:
        return "—"
    from apps.dms.models import TargetFileType

    item = TargetFileType.objects.filter(code=code, is_active=True).first()
    if item is not None:
        return item.name
    return FILE_TYPE_LABELS.get(code, code)


def step_statuses(target: dict) -> list[str]:
    if not (target.get("file_type_code") or "").strip():
        return ["pending"] * 6

    statuses = []
    statuses.append("done")
    statuses.append(
        "done"
        if (target.get("encoding_code") or "").strip()
        and (target.get("line_ending_code") or "").strip()
        else "pending"
    )
    layout = target.get("layout") or {}
    statuses.append("done" if layout else "pending")
    fields = target.get("fields") or []
    statuses.append("done" if fields else "draft")
    serialization = target.get("serialization") or {}
    statuses.append("done" if serialization else "pending")
    write_validation = target.get("write_validation") or {}
    statuses.append("done" if write_validation.get("policy") else "pending")
    return statuses
