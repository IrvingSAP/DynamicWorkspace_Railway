"""M4: enrutado job | pipeline | defer."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.file_pipeline.models import PipelineDefinition
from apps.file_scheduler.services import schedule_target as target_svc
from apps.file_watch.models import Watch, WatchAuditEvent
from apps.file_watch.services import watch_audit as audit_svc
from apps.file_watch.services import watch_errors as err
from apps.file_watch.services.watch_lifecycle_service import (
    MSG_FORBIDDEN,
    MSG_UNEXPECTED,
    MSG_VALIDATION,
    user_can_edit,
)
from apps.projects.models import Project

logger = logging.getLogger(__name__)

HELP = " Consulte la Ayuda para completar la información correctamente."
MSG_SAVED = "Enrutado guardado correctamente."
MSG_NEED_PROJECT = "Elija un proyecto con versión publicada." + HELP
MSG_NEED_PIPELINE = "Elija un pipeline activo con versión publicada." + HELP


def snapshot_from_watch(watch: Watch) -> dict:
    return {
        "route_mode": watch.route_mode or Watch.ROUTE_DEFER,
        "kind": watch.route_kind or "file_gate",
        "project_id": str(watch.route_project_id) if watch.route_project_id else "",
        "pipeline_id": str(watch.route_pipeline_id) if watch.route_pipeline_id else "",
    }


def posted_from_request(post) -> dict:
    return {
        "route_mode": (post.get("route_mode") or "").strip(),
        "kind": (post.get("kind") or "").strip(),
        "project_id": (post.get("project_id") or "").strip(),
        "pipeline_id": (post.get("pipeline_id") or "").strip(),
    }


def save_route(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure(err.FORBIDDEN, MSG_FORBIDDEN)

    mode = data.get("route_mode") or ""
    errors: dict[str, list[str]] = {}
    project = None
    pipeline = None
    kind = ""

    if mode not in {Watch.ROUTE_JOB, Watch.ROUTE_PIPELINE, Watch.ROUTE_DEFER}:
        errors.setdefault("route_mode", []).append("Seleccione Job, Pipeline o Diferir.")

    if mode == Watch.ROUTE_JOB and not errors.get("route_mode"):
        kind = data.get("kind") or ""
        if kind not in target_svc.FILE_JOB_KINDS:
            errors.setdefault("kind", []).append("Seleccione una app válida.")
        pid = data.get("project_id") or ""
        if not pid:
            errors.setdefault("project_id", []).append(MSG_NEED_PROJECT)
        else:
            try:
                project = Project.objects.select_related(
                    "dms_config", "dms_config__current_version", "company"
                ).get(pk=pid)
            except (Project.DoesNotExist, ValueError):
                errors.setdefault("project_id", []).append(MSG_NEED_PROJECT)
            else:
                if project.company_id != watch.company_id:
                    return OperationResult.failure(
                        err.ROUTE_CROSS_TENANT, err.MESSAGES.get(err.FORBIDDEN, MSG_FORBIDDEN)
                    )
                spec = target_svc.kind_spec(kind)
                if spec and project.project_kind != spec["project_kind"]:
                    errors.setdefault("project_id", []).append(
                        "El proyecto no corresponde a la app elegida."
                    )
                if target_svc.published_version_number(project) is None:
                    return OperationResult.failure(
                        err.NO_PUBLISHED,
                        err.MESSAGES[err.NO_PUBLISHED],
                        errors={"project_id": [err.MESSAGES[err.NO_PUBLISHED]]},
                    )

    if mode == Watch.ROUTE_PIPELINE and not errors.get("route_mode"):
        plid = data.get("pipeline_id") or ""
        if not plid:
            errors.setdefault("pipeline_id", []).append(MSG_NEED_PIPELINE)
        else:
            try:
                pipeline = PipelineDefinition.objects.select_related(
                    "current_version", "company"
                ).get(pk=plid)
            except (PipelineDefinition.DoesNotExist, ValueError):
                errors.setdefault("pipeline_id", []).append(MSG_NEED_PIPELINE)
            else:
                if pipeline.company_id != watch.company_id:
                    return OperationResult.failure(
                        err.ROUTE_CROSS_TENANT, err.MESSAGES.get(err.FORBIDDEN, MSG_FORBIDDEN)
                    )
                if (
                    pipeline.current_version_id is None
                    or pipeline.status != PipelineDefinition.STATUS_ACTIVE
                ):
                    return OperationResult.failure(
                        err.NO_PUBLISHED,
                        err.MESSAGES[err.NO_PUBLISHED],
                        errors={"pipeline_id": [err.MESSAGES[err.NO_PUBLISHED]]},
                    )

    if (
        mode == Watch.ROUTE_DEFER
        and watch.fire_mode == Watch.FIRE_ON_ARRIVAL
        and watch.fire_complete
    ):
        return OperationResult.failure(
            err.FIRE_ROUTE_CONFLICT,
            err.MESSAGES[err.FIRE_ROUTE_CONFLICT],
            errors={"route_mode": [err.MESSAGES[err.FIRE_ROUTE_CONFLICT]]},
        )

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    try:
        with transaction.atomic():
            watch.route_mode = mode
            watch.route_kind = kind if mode == Watch.ROUTE_JOB else ""
            watch.route_project = project if mode == Watch.ROUTE_JOB else None
            watch.route_pipeline = pipeline if mode == Watch.ROUTE_PIPELINE else None
            watch.route_saved_at = timezone.now()
            watch.save(
                update_fields=[
                    "route_mode",
                    "route_kind",
                    "route_project",
                    "route_pipeline",
                    "route_saved_at",
                    "updated_at",
                ]
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_ROUTE_UPDATED,
                user,
                {
                    "route_mode": mode,
                    "kind": kind,
                    "project_id": str(project.id) if project else "",
                    "pipeline_id": str(pipeline.id) if pipeline else "",
                },
            )
    except Exception:
        logger.exception("save_route unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(user_message=MSG_SAVED, payload={"watch": watch})
