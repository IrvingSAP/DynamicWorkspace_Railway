"""Persistencia de DmsSourceProfile y borrador DmsMappingVersion."""

import copy
import logging
import re

from django.db import transaction
from django.db.models import Max

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.models import DmsMappingVersion, DmsSourceProfile
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

FILE_TYPE_LABELS = {
    "txt_fixed": "TXT posicional",
    "txt_delimited": "TXT delimitado",
    "csv": "CSV",
    "xlsx": "Excel",
    "json": "JSON",
    "xml": "XML",
}


def default_source_dict() -> dict:
    """Perfil vacío para borradores nuevos (sin datos de ejemplo precargados)."""
    return {
        "file_type_code": "",
        "encoding_code": None,
        "encoding_custom": None,
        "line_ending_code": None,
        "line_ending_custom": None,
        "capture_start": {},
        "capture_end": {},
        "content_rules": {},
        "processing_report": {},
        "fields": [],
        "config": {},
    }


def user_can_edit_source(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def profile_to_dict(profile: DmsSourceProfile) -> dict:
    from apps.dms.source_profile.services.field_normalization_service import flatten_field_for_edit
    from apps.dms.transform_execution.services.capture_params import normalize_capture

    fields = [flatten_field_for_edit(item) for item in (profile.fields or [])]
    config = profile.config or {}
    return {
        "file_type_code": profile.file_type_code,
        "encoding_code": config.get("encoding_code") or "",
        "encoding_custom": config.get("encoding_custom"),
        "line_ending_code": config.get("line_ending_code") or "",
        "line_ending_custom": config.get("line_ending_custom"),
        "capture_start": normalize_capture(profile.capture_start or {}),
        "capture_end": normalize_capture(profile.capture_end or {}),
        "content_rules": profile.content_rules or {},
        "processing_report": profile.processing_report or {},
        "fields": fields,
        "config": config,
    }


def _apply_config_fields(data: dict, profile: DmsSourceProfile) -> None:
    config = dict(profile.config or {})
    for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
        if key in data:
            value = data[key]
            if value is None or value == "":
                config.pop(key, None)
            else:
                config[key] = value
    profile.config = config


def apply_dict_to_profile(profile: DmsSourceProfile, data: dict) -> None:
    if "file_type_code" in data:
        profile.file_type_code = (data.get("file_type_code") or "").strip()
    if "capture_start" in data:
        profile.capture_start = data["capture_start"] or {}
    if "capture_end" in data:
        profile.capture_end = data["capture_end"] or {}
    if "content_rules" in data:
        profile.content_rules = data["content_rules"] or {}
    if "processing_report" in data:
        profile.processing_report = data["processing_report"] or {}
    if "fields" in data:
        profile.fields = data["fields"] or []
    if "config" in data:
        profile.config = data["config"] or {}
    _apply_config_fields(data, profile)


def _line_value(capture: dict) -> int | None:
    from apps.dms.transform_execution.services.capture_params import capture_line

    return capture_line(capture)


def _effective_start_line(capture: dict) -> int | None:
    """Línea 1-based de inicio de datos cuando es comparable."""
    mode = (capture.get("mode") or "").strip()
    if mode == "first":
        return 1
    if mode == "line_number":
        return _line_value(capture)
    if mode == "after_header_block":
        try:
            skip = int(capture.get("skip_lines") or 0)
        except (TypeError, ValueError):
            return None
        return skip + 1
    return None


def _effective_end_line(capture: dict) -> int | None:
    """Línea 1-based de fin cuando es comparable (eof / percent / max_rows → None)."""
    mode = (capture.get("mode") or "").strip()
    if mode in ("line_number", "line_or_eof"):
        return _line_value(capture)
    return None


def flatten_validation_messages(bucket: dict[str, list[str]] | None) -> list[str]:
    messages: list[str] = []
    for items in (bucket or {}).values():
        messages.extend(items)
    return messages


def _flatten_messages(bucket: dict[str, list[str]]) -> list[str]:
    return flatten_validation_messages(bucket)


def validate_source_dict(
    data: dict,
    *,
    strict: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Valida el perfil de origen.

    Returns:
        (errors, warnings) — errores bloquean; advertencias no (source_definition.md § Validaciones).
    """
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    file_type = (data.get("file_type_code") or "").strip()
    if strict and not file_type:
        errors.setdefault("file_type_code", []).append("Seleccione un tipo de archivo.")

    fields = data.get("fields") or []
    if strict and not fields:
        errors.setdefault("fields", []).append("Defina al menos un campo.")

    names: set[str] = set()
    for field in fields:
        name = (field.get("name") or "").strip().lower()
        if not name:
            errors.setdefault("fields", []).append("Hay campos sin nombre.")
            continue
        if name in names:
            errors.setdefault("fields", []).append(f"Nombre de campo duplicado: «{name}».")
        names.add(name)

        content_type = (field.get("content_type") or "").strip()
        if content_type in ("date", "datetime"):
            if not (field.get("date_format") or "").strip():
                warnings.setdefault("fields", []).append(
                    f"Campo «{name}»: se recomienda indicar date_format para tipo {content_type}."
                )
        if content_type == "custom" and strict and not (field.get("pattern") or "").strip():
            errors.setdefault("fields", []).append(
                f"Campo «{name}»: indique pattern para tipo custom."
            )

    if file_type == "txt_fixed":
        from apps.dms.source_profile.services.field_normalization_service import (
            resolve_txt_fixed_bounds,
        )

        positional = []
        for field in fields:
            name = field.get("name", "?")
            bounds = resolve_txt_fixed_bounds(field)
            char = bounds.get("char") or ""
            start = bounds.get("start")
            end = bounds.get("end")
            length = bounds.get("length")

            if start is None and end is None and not char:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: indique inicio/fin, inicio/longitud o marcador char."
                )
                continue

            if char and start is None and end is None:
                # Solo marcador: sin rango para solapes; exigir longitud razonable si viene
                if length is not None and length < 1:
                    errors.setdefault("fields", []).append(
                        f"Campo «{name}»: la longitud debe ser ≥ 1."
                    )
                continue

            if start is None or end is None:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: no se pudo resolver el rango posicional."
                )
                continue
            if end < start:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: el fin debe ser ≥ al inicio."
                )
                continue
            if length is not None and length < 1:
                errors.setdefault("fields", []).append(
                    f"Campo «{name}»: la longitud debe ser ≥ 1."
                )
                continue
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

    capture_start = data.get("capture_start") or {}
    capture_end = data.get("capture_end") or {}
    if strict and not (capture_start.get("mode") or "").strip():
        errors.setdefault("capture_start", []).append("Defina el modo de inicio de captura.")
    if strict and not (capture_end.get("mode") or "").strip():
        errors.setdefault("capture_end", []).append("Defina el modo de fin de captura.")

    start_mode = (capture_start.get("mode") or "").strip()
    end_mode = (capture_end.get("mode") or "").strip()

    if end_mode == "percent":
        from apps.dms.transform_execution.services.capture_params import capture_percent

        percent = capture_percent(capture_end)
        if percent is None or percent < 1 or percent > 100:
            errors.setdefault("capture_end", []).append(
                "El porcentaje de fin debe estar entre 1 y 100."
            )
    if end_mode == "max_rows":
        try:
            max_rows = int(capture_end.get("max_rows"))
        except (TypeError, ValueError):
            max_rows = None
        if max_rows is None or max_rows < 1:
            errors.setdefault("capture_end", []).append(
                "El número máximo de filas debe ser ≥ 1."
            )
    if start_mode == "after_header_block":
        try:
            skip = int(capture_start.get("skip_lines") or 0)
        except (TypeError, ValueError):
            skip = -1
        if skip < 0:
            errors.setdefault("capture_start", []).append(
                "Las líneas a saltar deben ser ≥ 0."
            )
    if start_mode == "marker_start" and strict and not (capture_start.get("marker") or "").strip():
        errors.setdefault("capture_start", []).append("Indique el marcador de inicio.")
    if start_mode == "after_pattern":
        pattern = (capture_start.get("pattern") or "").strip()
        if strict and not pattern:
            errors.setdefault("capture_start", []).append("Indique el patrón regex de inicio.")
        elif pattern:
            try:
                re.compile(pattern)
            except re.error:
                errors.setdefault("capture_start", []).append(
                    "El patrón regex de inicio no es válido."
                )
    if end_mode == "marker_end" and strict and not (capture_end.get("marker") or "").strip():
        errors.setdefault("capture_end", []).append("Indique el marcador de fin.")
    if end_mode == "before_pattern":
        pattern = (capture_end.get("pattern") or "").strip()
        if strict and not pattern:
            errors.setdefault("capture_end", []).append("Indique el patrón regex de fin.")
        elif pattern:
            try:
                re.compile(pattern)
            except re.error:
                errors.setdefault("capture_end", []).append(
                    "El patrón regex de fin no es válido."
                )
    if start_mode == "after_blank_run":
        try:
            blank_count = int(capture_start.get("blank_count") or 0)
        except (TypeError, ValueError):
            blank_count = 0
        if blank_count < 1:
            errors.setdefault("capture_start", []).append(
                "El número de líneas en blanco debe ser ≥ 1."
            )
    if end_mode == "blank_run":
        try:
            blank_count = int(capture_end.get("blank_count") or 0)
        except (TypeError, ValueError):
            blank_count = 0
        if blank_count < 1:
            errors.setdefault("capture_end", []).append(
                "El número de líneas en blanco debe ser ≥ 1."
            )

    start_line = _effective_start_line(capture_start)
    end_line = _effective_end_line(capture_end)
    if start_line is not None and end_line is not None and end_line < start_line:
        errors.setdefault("capture_end", []).append(
            "La línea de fin debe ser posterior a la de inicio."
        )

    config = data.get("config") or {}
    if file_type in ("txt_delimited", "csv"):
        if strict and not (config.get("delimiter") or "").strip():
            errors.setdefault("config", []).append("Indique el delimitador del archivo.")
        if strict and config.get("has_header") is False and not fields:
            errors.setdefault("fields", []).append(
                "Sin encabezado debe definir al menos un campo con índice de columna."
            )
        indices: set[int] = set()
        for field in fields:
            name = (field.get("name") or "").strip()
            if not name:
                errors.setdefault("fields", []).append("Hay campos delimitados sin nombre.")
            try:
                column_index = int(field.get("column_index"))
            except (TypeError, ValueError):
                errors.setdefault("fields", []).append(
                    f"Campo «{field.get('name', '?')}»: índice de columna inválido."
                )
                continue
            if column_index in indices:
                errors.setdefault("fields", []).append(
                    f"Índice de columna duplicado: {column_index}."
                )
            indices.add(column_index)

    if file_type == "xlsx":
        if strict and not (config.get("sheet_name") or "").strip():
            errors.setdefault("config", []).append("Indique el nombre de la hoja Excel.")
        columns: set[str] = set()
        for field in fields:
            name = (field.get("name") or "").strip()
            column = (field.get("column") or "").strip().upper()
            if not name:
                errors.setdefault("fields", []).append("Hay campos Excel sin nombre.")
            if not column:
                errors.setdefault("fields", []).append(
                    f"Campo «{field.get('name', '?')}»: indique la columna."
                )
                continue
            if column in columns:
                errors.setdefault("fields", []).append(f"Columna duplicada: {column}.")
            columns.add(column)

    if file_type == "json":
        if strict and not (config.get("record_path") or "").strip():
            errors.setdefault("config", []).append(
                "Indique la ruta al arreglo de registros (record_path)."
            )
        json_paths: set[str] = set()
        for field in fields:
            name = (field.get("name") or "").strip()
            json_path = (field.get("json_path") or name).strip()
            if not name:
                errors.setdefault("fields", []).append("Hay campos JSON sin nombre.")
            if strict and not json_path:
                errors.setdefault("fields", []).append(
                    f"Campo «{field.get('name', '?')}»: indique json_path."
                )
            if json_path in json_paths:
                errors.setdefault("fields", []).append(
                    f"Ruta JSON duplicada: {json_path}."
                )
            json_paths.add(json_path)

    if file_type == "xml":
        if strict and not (config.get("record_element") or "").strip():
            errors.setdefault("config", []).append(
                "Indique el elemento repetido del XML (record_element)."
            )
        elements: set[str] = set()
        for field in fields:
            name = (field.get("name") or "").strip()
            element = (field.get("element") or name).strip()
            if not name:
                errors.setdefault("fields", []).append("Hay campos XML sin nombre.")
            if strict and not element:
                errors.setdefault("fields", []).append(
                    f"Campo «{field.get('name', '?')}»: indique element."
                )
            if element in elements:
                errors.setdefault("fields", []).append(f"Elemento XML duplicado: {element}.")
            elements.add(element)

    report = data.get("processing_report") or {}
    if report.get("report_enabled"):
        if not report.get("include_summary") and not report.get("include_row_errors"):
            warnings.setdefault("processing_report", []).append(
                "Con informe habilitado, se recomienda incluir resumen o detalle por fila."
            )

    return errors, warnings


@transaction.atomic
def get_or_create_draft_version(project: Project) -> DmsMappingVersion:
    from apps.dms.field_mapping.services import field_mapping_persistence_service
    from apps.dms.target_profile.services import target_persistence_service

    version = (
        DmsMappingVersion.objects.filter(
            project=project,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        .select_related("source_profile")
        .order_by("-version_number")
        .first()
    )
    if version is not None:
        DmsSourceProfile.objects.get_or_create(
            version=version,
            defaults=_profile_defaults_from_dict(default_source_dict()),
        )
        target_persistence_service.ensure_target_on_version(version)
        field_mapping_persistence_service.ensure_mapping_set_on_version(version)
        return version

    last_number = (
        DmsMappingVersion.objects.filter(project=project).aggregate(
            max_num=Max("version_number")
        )["max_num"]
        or 0
    )
    version = DmsMappingVersion.objects.create(
        project=project,
        version_number=last_number + 1,
        status=DmsMappingVersion.STATUS_DRAFT,
    )
    DmsSourceProfile.objects.create(
        version=version,
        **_profile_defaults_from_dict(default_source_dict()),
    )
    target_persistence_service.ensure_target_on_version(version)
    field_mapping_persistence_service.ensure_mapping_set_on_version(version)
    return version


def profile_defaults_from_dict(data: dict) -> dict:
    return _profile_defaults_from_dict(data)


def _profile_defaults_from_dict(data: dict) -> dict:
    config = dict(data.get("config") or {})
    for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
        if key in data and data[key] is not None:
            config[key] = data[key]
    return {
        "file_type_code": data.get("file_type_code", ""),
        "capture_start": data.get("capture_start") or {},
        "capture_end": data.get("capture_end") or {},
        "content_rules": data.get("content_rules") or {},
        "processing_report": data.get("processing_report") or {},
        "fields": data.get("fields") or [],
        "config": config,
    }


def get_source_dict(project: Project) -> dict:
    version = get_or_create_draft_version(project)
    profile = version.source_profile
    return profile_to_dict(profile)


def ensure_step4_coherence(project: Project) -> dict:
    from apps.dms.source_profile.services.source_profile_service import (
        default_config_for_type,
        default_fields_for_type,
        fields_match_variant,
        get_step4_variant,
    )

    version = get_or_create_draft_version(project)
    profile = version.source_profile
    source = profile_to_dict(profile)
    file_type = source.get("file_type_code", "")
    variant = get_step4_variant(file_type)
    if variant == "unsupported" or not file_type:
        return source

    fields = source.get("fields") or []
    config = source.get("config") or {}
    typed_config = default_config_for_type(file_type, config)
    config_changed = typed_config != config

    # Sin campos: no sembramos demo en BD; solo alineamos config tipada si hace falta.
    if not fields:
        if config_changed:
            apply_dict_to_profile(profile, {"config": typed_config})
            profile.save(update_fields=["config", "updated_at"])
            version.save(update_fields=["updated_at"])
            return profile_to_dict(profile)
        return source

    needs_update = not fields_match_variant(fields, variant) or config_changed
    if not needs_update:
        return source

    # Tipo cambió y los campos no encajan: limpia para que el usuario redefine en paso 4.
    if not fields_match_variant(fields, variant):
        source["fields"] = []
    source["config"] = typed_config
    from apps.dms.source_profile.services.field_normalization_service import normalize_fields_list

    source["fields"] = normalize_fields_list(source["fields"], file_type)
    apply_dict_to_profile(profile, source)
    profile.save()
    version.save(update_fields=["updated_at"])
    return profile_to_dict(profile)


def get_draft_version(project: Project) -> DmsMappingVersion:
    return get_or_create_draft_version(project)


def merge_source_dict(current: dict, partial: dict) -> dict:
    from apps.dms.transform_execution.services.capture_params import normalize_capture

    merged = copy.deepcopy(current)
    replace_keys = {"capture_start", "capture_end"}
    merge_keys = {"content_rules", "processing_report", "config"}
    for key, value in partial.items():
        if key in replace_keys:
            merged[key] = normalize_capture(
                value if isinstance(value, dict) else {}
            )
        elif key in merge_keys:
            if isinstance(value, dict):
                base = merged.get(key) or {}
                merged[key] = {**base, **value}
            else:
                merged[key] = value
        else:
            merged[key] = value
    if "capture_start" in merged:
        merged["capture_start"] = normalize_capture(merged.get("capture_start"))
    if "capture_end" in merged:
        merged["capture_end"] = normalize_capture(merged.get("capture_end"))
    return merged


def save_source(
    user,
    project: Project,
    partial: dict,
    *,
    strict: bool = False,
) -> OperationResult:
    if not user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar la definición de origen.",
        )

    version = get_or_create_draft_version(project)
    profile = version.source_profile
    current = profile_to_dict(profile)
    merged = merge_source_dict(current, partial)

    new_type = (merged.get("file_type_code") or "").strip()
    old_type = (current.get("file_type_code") or "").strip()
    if new_type and new_type != old_type:
        from apps.dms.source_profile.services.source_profile_service import (
            default_config_for_type,
        )

        # Campos se definen en el paso 4; no precargar ejemplos de demo.
        merged["fields"] = []
        preserved_config = dict(merged.get("config") or {})
        for key in ("encoding_code", "encoding_custom", "line_ending_code", "line_ending_custom"):
            value = preserved_config.get(key) or merged.get(key) or current.get(key)
            if value:
                preserved_config[key] = value
        merged["config"] = default_config_for_type(new_type, preserved_config)

    from apps.dms.source_profile.services.field_normalization_service import normalize_fields_list

    merged["fields"] = normalize_fields_list(
        merged.get("fields") or [],
        merged.get("file_type_code") or "",
    )

    errors, warnings = validate_source_dict(merged, strict=strict)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del perfil de origen.",
            errors=errors,
            warnings=warnings,
        )

    try:
        apply_dict_to_profile(profile, merged)
        profile.save()
        version.save(update_fields=["updated_at"])
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("save_source unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Perfil de origen guardado correctamente.",
        payload={
            "source": profile_to_dict(profile),
            "version": version,
            "warnings": warnings,
            "warning_messages": _flatten_messages(warnings),
        },
    )


def file_type_label(code: str) -> str:
    if not code:
        return "—"
    from apps.dms.models import SourceFileType

    item = SourceFileType.objects.filter(code=code, is_active=True).first()
    if item is not None:
        return item.name
    return FILE_TYPE_LABELS.get(code, code)


def step_statuses(source: dict) -> list[str]:
    if not (source.get("file_type_code") or "").strip():
        return ["pending"] * 6

    statuses = []
    statuses.append("done")
    statuses.append("done" if source.get("capture_start", {}).get("mode") else "pending")
    statuses.append("done" if source.get("capture_end", {}).get("mode") else "pending")
    fields = source.get("fields") or []
    statuses.append("done" if fields else "draft")
    rules = source.get("content_rules") or {}
    statuses.append("done" if rules else "pending")
    report = source.get("processing_report") or {}
    statuses.append("done" if report else "pending")
    return statuses
