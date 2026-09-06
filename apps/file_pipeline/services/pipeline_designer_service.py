"""Diseñador de pasos (M2): rail de borrador."""

from __future__ import annotations

import json
import logging

from django.db.models import Q
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.mapping.models import DmsProjectConfig
from apps.file_pipeline.models import PipelineDefinition, PipelineMembership
from apps.file_pipeline.services import pipeline_project_service as lifecycle
from apps.file_pipeline.services import pipeline_step_catalog as catalog
from apps.projects.models import Project, ProjectMembership

logger = logging.getLogger(__name__)

MSG_SAVED = "Borrador de pasos guardado."
MSG_SAVED_INCOMPLETE = (
    "Borrador guardado. Diseñar pasos sigue pendiente: añada al menos un paso válido."
)
MSG_NO_EDIT = "No tiene permiso para editar el diseñador de este pipeline."
MSG_INVALID_STEPS = "Revise los pasos del rail; no se pudo guardar."


def user_can_edit_design(user, pipeline: PipelineDefinition) -> bool:
    membership = lifecycle.get_membership(user, pipeline)
    if membership is None:
        return False
    return membership.role in {
        PipelineMembership.ROLE_PA,
        PipelineMembership.ROLE_ED,
    }


def visible_projects_for_kind(user, pipeline: PipelineDefinition, kind: str) -> list[dict]:
    spec = catalog.get_kind(kind, company=pipeline.company)
    if spec is None:
        return []
    company = pipeline.company
    project_kind = spec["project_kind"]
    member_ids = ProjectMembership.objects.filter(
        user=user,
        is_active=True,
        project__company=company,
        project__project_kind=project_kind,
    ).values_list("project_id", flat=True)
    qs = (
        Project.objects.filter(
            company=company,
            project_kind=project_kind,
            is_archived=False,
        )
        .filter(
            Q(id__in=member_ids)
            | Q(dms_config__visibility=DmsProjectConfig.VISIBILITY_COMPANY)
        )
        .select_related("dms_config")
        .distinct()
        .order_by("slug")
    )
    rows = []
    for project in qs:
        config = getattr(project, "dms_config", None)
        if config is None or not config.current_version_id:
            continue
        rows.append(
            {
                "slug": project.slug,
                "name": project.name,
                "label": f"{project.slug} — {project.name} (activo)",
            }
        )
    return rows


def _normalize_steps(raw_steps, user, pipeline: PipelineDefinition) -> tuple[list[dict], dict]:
    errors: dict[str, list[str]] = {}
    if not isinstance(raw_steps, list):
        errors["steps"] = ["El rail de pasos no es válido."]
        return [], errors

    seen_order = set()
    cleaned: list[dict] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            errors.setdefault("steps", []).append(f"Paso {index + 1} inválido.")
            continue
        kind = str(raw.get("kind") or "").strip()
        slug = str(raw.get("project_slug") or "").strip().lower()
        spec = catalog.get_kind(kind, company=pipeline.company)
        if spec is None:
            errors.setdefault("steps", []).append(
                f"Paso {index + 1}: tipo no está en el catálogo habilitado."
            )
            continue
        allowed = {row["slug"] for row in visible_projects_for_kind(user, pipeline, kind)}
        if slug not in allowed:
            errors.setdefault("steps", []).append(
                f"Paso {index + 1}: proyecto no autorizado, inactivo o sin versión publicada."
            )
            continue
        order = index + 1
        if order in seen_order:
            errors.setdefault("steps", []).append("Hay órdenes duplicados.")
            continue
        seen_order.add(order)
        input_from = "pipeline_input" if order == 1 else "previous"
        cleaned.append(
            {
                "order": order,
                "kind": kind,
                "project_slug": slug,
                "on_error": "stop",
                "input_from": input_from,
                "label": catalog.short_label(kind),
            }
        )
    return cleaned, errors


def save_draft(user, pipeline: PipelineDefinition, raw_steps) -> OperationResult:
    if not user_can_edit_design(user, pipeline):
        return OperationResult.failure("forbidden", MSG_NO_EDIT)

    steps, errors = _normalize_steps(raw_steps, user, pipeline)
    if errors:
        return OperationResult.failure(
            "validation_form",
            MSG_INVALID_STEPS,
            errors=errors,
        )

    labels = [step["label"] for step in steps]
    pipeline.draft_steps = steps
    pipeline.draft_step_labels = labels
    if len(steps) >= 1:
        pipeline.design_saved_at = timezone.now()
        message = MSG_SAVED
    else:
        pipeline.design_saved_at = None
        message = MSG_SAVED_INCOMPLETE
    try:
        pipeline.save(
            update_fields=[
                "draft_steps",
                "draft_step_labels",
                "design_saved_at",
                "updated_at",
            ]
        )
    except Exception:
        logger.exception("save_pipeline_draft unexpected slug=%s", pipeline.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=message, payload={"steps": steps})


def parse_steps_payload(post) -> list:
    raw = post.get("steps_json", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return data
