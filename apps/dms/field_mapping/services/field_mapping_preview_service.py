"""Preview de FieldMapping sobre una fila origen (field_mapping.md)."""

from __future__ import annotations

import logging

from apps.core.services.operation_result import OperationResult
from apps.dms.field_mapping.services.field_normalization_service import (
    normalize_mappings_list,
)
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.services import target_persistence_service
from apps.dms.transform_execution.services.row_mapping_service import (
    GeneratorState,
    map_row,
)

logger = logging.getLogger(__name__)


def preview_mappings(
    project,
    *,
    mappings: list | None,
    source_row: dict | None,
    row_number: int = 1,
) -> OperationResult:
    source = source_persistence_service.get_source_dict(project)
    target = target_persistence_service.get_target_dict(project)
    normalized = normalize_mappings_list(mappings or [])
    row = {}
    for key, value in (source_row or {}).items():
        name = str(key or "").strip().lower()
        if name:
            row[name] = value
    try:
        number = max(1, int(row_number or 1))
    except (TypeError, ValueError):
        number = 1

    try:
        target_row, errors = map_row(
            row,
            normalized,
            target.get("fields") or [],
            row_number=number,
            generators=GeneratorState(),
        )
    except Exception:
        logger.exception("preview_mappings unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al calcular el preview.",
        )

    return OperationResult.success(
        user_message="Preview de mapeo listo.",
        payload={
            "source_row": row,
            "target_row": target_row,
            "row_errors": errors,
            "source_fields": source.get("fields") or [],
            "target_fields": target.get("fields") or [],
        },
    )
