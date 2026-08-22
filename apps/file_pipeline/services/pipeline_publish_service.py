"""Publicar versión de File Pipeline (M3)."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.file_pipeline.models import (
    PipelineDefinition,
    PipelineStepKind,
    PipelineVersion,
)
from apps.file_pipeline.services import pipeline_catalog_service as catalog
from apps.file_pipeline.services import pipeline_designer_service as designer
from apps.file_pipeline.services import pipeline_project_service as lifecycle
from apps.projects.models import Project

logger = logging.getLogger(__name__)

MSG_PUBLISH_BLOCKED = lifecycle.MSG_PUBLISH_BLOCKED
MSG_NO_PUBLISH = "No tiene permiso para publicar este pipeline."
MSG_CHECKS = "No se puede publicar. Revise el checklist."
MSG_OK = (
    "Versión v{n} publicada correctamente. El borrador queda abierto para v{next}."
)


def user_can_publish(user, pipeline: PipelineDefinition) -> bool:
    return designer.user_can_edit_design(user, pipeline)


def current_published(pipeline: PipelineDefinition) -> PipelineVersion | None:
    if pipeline.current_version_id:
        return pipeline.current_version
    return (
        PipelineVersion.objects.filter(
            pipeline=pipeline,
            status=PipelineVersion.STATUS_PUBLISHED,
        )
        .order_by("-version_number")
        .first()
    )


def next_version_number(pipeline: PipelineDefinition) -> int:
    agg = PipelineVersion.objects.filter(pipeline=pipeline).aggregate(
        m=Max("version_number")
    )
    current = agg["m"] or 0
    return current + 1


def _project_for_step(pipeline: PipelineDefinition, slug: str) -> Project | None:
    return Project.objects.filter(
        company=pipeline.company,
        slug=slug,
        is_archived=False,
    ).select_related("dms_config").first()


def evaluate_checks(user, pipeline: PipelineDefinition) -> list[dict]:
    steps = list(pipeline.draft_steps or [])
    design_ok = pipeline.design_complete and len(steps) >= 1

    p2_ok, p2_detail = True, "kinds en catálogo"
    p3_ok, p3_detail = True, "proyectos con versión publicada"
    p4_ok, p4_detail = True, "handoffs tipados"
    p5_ok, p5_detail = True, "permisos sobre proyectos de paso"

    if not design_ok:
        p2_ok = p3_ok = p4_ok = p5_ok = False
        p2_detail = p3_detail = p4_detail = p5_detail = "Pendiente de Diseñar pasos"
        return [
            {
                "code": "P1",
                "ok": False,
                "label": "≥1 paso guardado en Diseñar",
            },
            {"code": "P2", "ok": False, "label": p2_detail},
            {"code": "P3", "ok": False, "label": p3_detail},
            {"code": "P4", "ok": False, "label": p4_detail},
            {"code": "P5", "ok": False, "label": p5_detail},
        ]

    kinds_fail: list[str] = []
    proj_fail: list[str] = []
    handoff_fail: list[str] = []
    perm_fail: list[str] = []
    rows_by_kind = {row.kind: row for row in PipelineStepKind.objects.all()}
    resolved: list[PipelineStepKind | None] = []

    for index, step in enumerate(steps):
        order = index + 1
        kind = str((step or {}).get("kind") or "").strip()
        slug = str((step or {}).get("project_slug") or "").strip().lower()
        spec = catalog.get_kind(kind, company=pipeline.company)
        row = rows_by_kind.get(kind)
        resolved.append(row)
        if spec is None or row is None:
            kinds_fail.append(f"paso {order}: {kind or '—'}")
            continue
        project = _project_for_step(pipeline, slug)
        if project is None:
            proj_fail.append(f"paso {order}: {slug or 'sin proyecto'}")
            continue
        if project.project_kind != spec["project_kind"]:
            kinds_fail.append(f"paso {order}: kind ≠ project_kind")
        config = getattr(project, "dms_config", None)
        if config is None or not config.current_version_id:
            proj_fail.append(f"paso {order}: {slug} sin versión publicada")
        allowed = {
            item["slug"]
            for item in designer.visible_projects_for_kind(user, pipeline, kind)
        }
        if slug not in allowed:
            perm_fail.append(f"paso {order}: {slug}")

    prev_row = None
    for index, row in enumerate(resolved):
        order = index + 1
        expected = "pipeline_input" if order == 1 else "previous"
        got = str((steps[index] or {}).get("input_from") or expected)
        if got != expected:
            handoff_fail.append(f"paso {order}: input_from")
        if row is None:
            prev_row = None
            continue
        if row.input_arity == "foreach":
            handoff_fail.append(f"paso {order}: foreach no soportado al publicar")
        # file_match (arity 2): el rail lineal entrega 1 archivo (entrada A).
        # A/B se define en options (fase posterior); no bloquea P4.
        if prev_row is not None:
            if not prev_row.produces_file:
                handoff_fail.append(
                    f"paso {order}: el anterior no produce archivo para el handoff"
                )
            if prev_row.output_arity == "N" and row.input_arity == "1":
                handoff_fail.append(
                    f"paso {order}: Split (N) no puede alimentar un paso de 1 archivo"
                )
        prev_row = row

    if kinds_fail:
        p2_ok = False
        p2_detail = "Kind no habilitado: " + "; ".join(kinds_fail[:4])
    if proj_fail:
        p3_ok = False
        p3_detail = "Proyecto inválido: " + "; ".join(proj_fail[:4])
    if handoff_fail:
        p4_ok = False
        p4_detail = "Handoff: " + "; ".join(handoff_fail[:4])
    if perm_fail:
        p5_ok = False
        p5_detail = "Sin permiso en: " + "; ".join(perm_fail[:4])

    match_steps = [
        f"paso {i + 1}"
        for i, row in enumerate(resolved)
        if row is not None and row.kind == "file_match"
    ]
    if p4_ok and match_steps:
        p4_detail = (
            "handoffs tipados · File Match usará el archivo previo como entrada A "
            "(entrada B / options en fase posterior)"
        )

    return [
        {
            "code": "P1",
            "ok": True,
            "label": f"≥1 paso ({len(steps)})",
        },
        {"code": "P2", "ok": p2_ok, "label": p2_detail},
        {"code": "P3", "ok": p3_ok, "label": p3_detail},
        {"code": "P4", "ok": p4_ok, "label": p4_detail},
        {"code": "P5", "ok": p5_ok, "label": p5_detail},
    ]


def _snapshot_steps(pipeline: PipelineDefinition) -> list[dict]:
    frozen = []
    for index, step in enumerate(pipeline.draft_steps or []):
        kind = str((step or {}).get("kind") or "").strip()
        slug = str((step or {}).get("project_slug") or "").strip().lower()
        spec = catalog.get_kind(kind, company=pipeline.company)
        project = _project_for_step(pipeline, slug)
        frozen.append(
            {
                "order": index + 1,
                "kind": kind,
                "label": (spec or {}).get("short") or kind,
                "project_slug": slug,
                "project_kind": (spec or {}).get("project_kind") or "",
                "on_error": "stop",
                "input_from": "pipeline_input" if index == 0 else "previous",
            }
        )
        if project is not None:
            frozen[-1]["project_id"] = str(project.id)
    return frozen


def get_publish_context(user, pipeline: PipelineDefinition) -> dict:
    published = current_published(pipeline)
    next_n = next_version_number(pipeline)
    checks = evaluate_checks(user, pipeline)
    all_ok = all(item["ok"] for item in checks)
    can_edit = user_can_publish(user, pipeline)
    blocked = ""
    if not pipeline.design_complete:
        blocked = MSG_PUBLISH_BLOCKED
    elif not all_ok:
        blocked = MSG_CHECKS
    elif not can_edit:
        blocked = MSG_NO_PUBLISH
    return {
        "next_version_number": next_n,
        "published_version_number": published.version_number if published else None,
        "published_version_label": (
            f"v{published.version_number}" if published else "ninguna"
        ),
        "checks": checks,
        "can_publish": all_ok and can_edit,
        "can_edit": can_edit,
        "publish_blocked_reason": blocked,
        "steps": pipeline.draft_steps or [],
        "history": list(
            PipelineVersion.objects.filter(
                pipeline=pipeline,
                status=PipelineVersion.STATUS_PUBLISHED,
            )
            .select_related("published_by")
            .order_by("-version_number")[:12]
        ),
    }


def publish_pipeline(user, pipeline: PipelineDefinition) -> OperationResult:
    if not user_can_publish(user, pipeline):
        return OperationResult.failure("forbidden", MSG_NO_PUBLISH)
    if not pipeline.design_complete:
        return OperationResult.failure("design_incomplete", MSG_PUBLISH_BLOCKED)
    checks = evaluate_checks(user, pipeline)
    if not all(item["ok"] for item in checks):
        errors = {
            item["code"]: [item["label"]] for item in checks if not item["ok"]
        }
        return OperationResult.failure(
            "validation_form",
            MSG_CHECKS,
            errors=errors,
        )
    number = next_version_number(pipeline)
    snapshot = _snapshot_steps(pipeline)
    now = timezone.now()
    try:
        with transaction.atomic():
            version = PipelineVersion.objects.create(
                pipeline=pipeline,
                version_number=number,
                status=PipelineVersion.STATUS_PUBLISHED,
                steps=snapshot,
                published_at=now,
                published_by=user,
            )
            pipeline.current_version = version
            pipeline.save(update_fields=["current_version", "updated_at"])
    except Exception:
        logger.exception("publish_pipeline slug=%s", pipeline.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al publicar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(
        user_message=MSG_OK.format(n=number, next=number + 1),
        payload={
            "version": version,
            "published_version_number": number,
            "new_draft_version_number": number + 1,
        },
    )
