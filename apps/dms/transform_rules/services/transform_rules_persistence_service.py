"""Persistencia de transform_pipeline sobre DmsFieldMappingSet."""

import copy
import logging

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.field_mapping.services import field_mapping_persistence_service
from apps.dms.field_mapping.services.field_normalization_service import normalize_mappings_list
from apps.dms.transform_rules.services.pipeline_engine_service import (
    PipelineApplyError,
    apply_pipeline,
)
from apps.dms.transform_rules.services.transform_catalog_service import (
    MAX_PIPELINE_STEPS,
    active_transform_op_codes,
    normalize_pipeline,
)
from apps.projects.models import Project

logger = logging.getLogger(__name__)


def user_can_edit_rules(user, project: Project) -> bool:
    return field_mapping_persistence_service.user_can_edit_mappings(user, project)


def validate_pipeline_steps(
    steps: list,
    *,
    field_label: str = "",
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    prefix = f"Campo «{field_label}»: " if field_label else ""
    pipeline = normalize_pipeline(steps)

    if len(pipeline) > MAX_PIPELINE_STEPS:
        warnings.append(
            f"{prefix}el pipeline supera {MAX_PIPELINE_STEPS} pasos; revise si puede simplificarse."
        )

    allowed = active_transform_op_codes()
    for index, step in enumerate(pipeline, start=1):
        op = step.get("op") or ""
        step_label = f"{prefix}paso {index}"
        if not op:
            errors.append(f"{step_label}: falta op.")
            continue
        if op not in allowed:
            errors.append(f"{step_label}: operación «{op}» no válida o inactiva.")
            continue

        if op == "date_format":
            if not (step.get("format") or "").strip():
                errors.append(f"{step_label}: date_format requiere format.")
        elif op in {"pad_left", "pad_right"}:
            try:
                length = int(step.get("length"))
            except (TypeError, ValueError):
                length = 0
            if length <= 0:
                errors.append(f"{step_label}: {op} requiere length > 0.")
            char = step.get("char")
            if char in (None, ""):
                errors.append(f"{step_label}: {op} requiere char.")
            elif len(str(char)) != 1:
                errors.append(f"{step_label}: {op} char debe ser un solo carácter.")
        elif op == "default_if_empty":
            if "value" not in step:
                warnings.append(
                    f"{step_label}: default_if_empty sin value; se usará cadena vacía."
                )
        elif op == "replace_map":
            if not isinstance(step.get("map"), dict) or not step.get("map"):
                errors.append(f"{step_label}: replace_map requiere map.")
        elif op == "replace":
            if step.get("find") in (None, ""):
                errors.append(f"{step_label}: replace requiere find.")
        elif op == "substring":
            try:
                int(step.get("start") or 0)
            except (TypeError, ValueError):
                errors.append(f"{step_label}: substring start inválido.")
        elif op == "regex_extract":
            if not str(step.get("pattern") or "").strip():
                errors.append(f"{step_label}: regex_extract requiere pattern.")
        elif op == "number_format":
            try:
                places = int(
                    step.get("decimal_places")
                    if step.get("decimal_places") is not None
                    else 2
                )
            except (TypeError, ValueError):
                places = -1
            if places < 0:
                errors.append(f"{step_label}: number_format decimal_places inválido.")

    return errors, warnings


def validate_mappings_pipelines(
    mappings: list,
    *,
    strict: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    for mapping in mappings or []:
        if not mapping.get("is_active", True):
            continue
        target = (mapping.get("target_field") or "").strip()
        step_errors, step_warnings = validate_pipeline_steps(
            mapping.get("transform_pipeline") or [],
            field_label=target or "?",
        )
        if step_errors:
            errors.setdefault("transform_pipeline", []).extend(step_errors)
        if step_warnings:
            warnings.setdefault("transform_pipeline", []).extend(step_warnings)

    if strict and errors:
        return errors, warnings
    return errors, warnings


def preview_value(sample: str, steps: list) -> OperationResult:
    pipeline = normalize_pipeline(steps)
    step_errors, _warnings = validate_pipeline_steps(pipeline)
    if step_errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos de las reglas de transformación.",
            errors={"transform_pipeline": step_errors},
        )
    try:
        result = apply_pipeline(sample, pipeline, raise_on_error=True)
    except PipelineApplyError as exc:
        return OperationResult.failure(
            "validation_form",
            str(exc),
            errors={"transform_pipeline": [str(exc)]},
        )
    except Exception:
        logger.exception("preview_value unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al previsualizar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(
        user_message="Preview generado.",
        payload={"input": sample, "output": result, "pipeline": pipeline},
    )


def preview_with_sample_row(
    project: Project,
    *,
    target_field: str,
    steps: list,
    source_row: dict | None = None,
) -> OperationResult:
    """
    Resuelve el valor post-mapeo (sin pipeline guardado) desde la fila muestra
    y aplica el pipeline del editor.
    """
    from apps.dms.field_mapping.services.field_mapping_service import get_sample_preview_row
    from apps.dms.transform_execution.services.row_mapping_service import (
        GeneratorState,
        MappingError,
        resolve_mapping_value,
    )

    target = (target_field or "").strip().lower()
    if not target:
        return OperationResult.failure(
            "validation_form",
            "Seleccione un campo destino.",
            errors={"target_field": ["Campo destino requerido."]},
        )

    row = source_row if isinstance(source_row, dict) else None
    if row is None:
        row = get_sample_preview_row(project)
    if not row:
        return OperationResult.failure(
            "validation_form",
            "No hay archivo muestra parseable. Suba una muestra o use un valor literal.",
        )

    mappings = field_mapping_persistence_service.get_mappings_dict(project).get("mappings") or []
    mapping = next(
        (
            item
            for item in mappings
            if item.get("is_active", True)
            and (item.get("target_field") or "").strip().lower() == target
        ),
        None,
    )
    if mapping is None:
        return OperationResult.failure(
            "validation_form",
            f"No hay mapeo activo para «{target}».",
        )

    mapping_no_pipe = dict(mapping)
    mapping_no_pipe["transform_pipeline"] = []
    try:
        mapped_value = resolve_mapping_value(
            mapping_no_pipe,
            {str(k).strip().lower(): v for k, v in row.items()},
            row_number=1,
            generators=GeneratorState(),
        )
    except MappingError as exc:
        return OperationResult.failure(
            "validation_form",
            str(exc),
            errors={"mapping": [str(exc)]},
        )
    except Exception:
        logger.exception("preview_with_sample_row resolve unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al resolver el valor de mapeo para el preview.",
        )

    sample_text = "" if mapped_value is None else str(mapped_value)
    result = preview_value(sample_text, steps)
    if not result.ok:
        return result
    payload = dict(result.payload or {})
    payload["from_sample"] = True
    payload["target_field"] = target
    return OperationResult.success(user_message=result.user_message, payload=payload)


def list_pipeline_templates(*, active_only: bool = True) -> list[dict]:
    try:
        from apps.dms.models import TransformPipelineTemplate

        qs = TransformPipelineTemplate.objects.all().order_by("sort_order", "code")
        if active_only:
            qs = qs.filter(is_active=True)
        rows = list(qs)
        if rows:
            return [
                {
                    "code": row.code,
                    "name": row.name,
                    "description": row.description or "",
                    "pipeline": list(row.pipeline or []),
                }
                for row in rows
            ]
    except Exception:
        pass
    return [
        {
            "code": "normalize_text",
            "name": "Normalizar texto",
            "description": "trim + upper",
            "pipeline": [{"op": "trim"}, {"op": "upper"}],
        },
        {
            "code": "date_iso",
            "name": "Fecha ISO",
            "description": "date_format %Y-%m-%d",
            "pipeline": [
                {"op": "trim"},
                {
                    "op": "date_format",
                    "format": "%Y-%m-%d",
                    "input_formats": ["%d/%m/%Y", "%Y-%m-%d"],
                },
            ],
        },
        {
            "code": "blank_to_na",
            "name": "Vacío → N/A",
            "description": "default_if_empty",
            "pipeline": [{"op": "default_if_empty", "value": "N/A"}],
        },
    ]


@transaction.atomic
def save_pipelines(
    user,
    project: Project,
    pipelines_by_target: dict,
    *,
    strict: bool = False,
) -> OperationResult:
    if not user_can_edit_rules(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar las reglas de transformación.",
        )

    version = field_mapping_persistence_service.get_or_create_draft_with_mappings(project)
    mapping_set = version.field_mapping_set
    current = field_mapping_persistence_service.set_to_dict(mapping_set)
    merged = copy.deepcopy(current)
    mappings = normalize_mappings_list(merged.get("mappings") or [])

    by_target = {
        str(target).strip().lower(): normalize_pipeline(steps)
        for target, steps in (pipelines_by_target or {}).items()
        if str(target).strip()
    }

    if not mappings:
        return OperationResult.failure(
            "validation_form",
            "Defina al menos un mapeo antes de configurar reglas.",
        )

    known = {(item.get("target_field") or "") for item in mappings}
    unknown = [name for name in by_target if name not in known]
    if unknown:
        return OperationResult.failure(
            "validation_form",
            "Hay reglas para campos sin mapeo activo.",
            errors={
                "transform_pipeline": [
                    f"Campo «{name}» no tiene mapeo; cree el mapeo primero."
                    for name in unknown
                ]
            },
        )

    for item in mappings:
        target = item.get("target_field") or ""
        if target in by_target:
            item["transform_pipeline"] = by_target[target]

    pipe_errors, pipe_warnings = validate_mappings_pipelines(mappings, strict=strict)
    if pipe_errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos de las reglas de transformación.",
            errors=pipe_errors,
            warnings=pipe_warnings,
        )

    # Reuse mapping validation (non-strict) so mappings stay coherent
    from apps.dms.source_profile.services import source_persistence_service
    from apps.dms.target_profile.services import target_persistence_service

    source_dict = source_persistence_service.get_source_dict(project)
    target_dict = target_persistence_service.get_target_dict(project)
    map_errors, map_warnings = field_mapping_persistence_service.validate_mappings_dict(
        {"mappings": mappings},
        source_fields=source_dict.get("fields") or [],
        target_fields=target_dict.get("fields") or [],
        strict=False,
    )
    if map_errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del mapeo de campos.",
            errors=map_errors,
            warnings={**map_warnings, **pipe_warnings},
        )

    try:
        field_mapping_persistence_service.apply_dict_to_set(
            mapping_set, {"mappings": mappings}
        )
        mapping_set.save()
        version.save(update_fields=["updated_at"])
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("save_pipelines unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    warnings = {**map_warnings, **pipe_warnings}
    return OperationResult.success(
        user_message="Reglas de transformación guardadas correctamente.",
        payload={
            "mappings": field_mapping_persistence_service.set_to_dict(mapping_set)["mappings"],
            "warnings": warnings,
            "warning_messages": field_mapping_persistence_service.flatten_validation_messages(
                warnings
            ),
        },
    )


def is_rules_configured(project: Project) -> bool:
    """True si hay mapeos y al menos un pipeline no vacío, o todos vacíos pero sin errores."""
    data = field_mapping_persistence_service.get_mappings_dict(project)
    mappings = [m for m in (data.get("mappings") or []) if m.get("is_active", True)]
    if not mappings:
        return False
    errors, _warnings = validate_mappings_pipelines(mappings, strict=True)
    return not errors
