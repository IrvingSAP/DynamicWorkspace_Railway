"""Bridge FILE GATE — FILE MATCH Módulo 8 (gate_bridge.md).

Envoltorio delgado sobre dms_bridge_service: settings + pre-check dual A/B.
"""

from __future__ import annotations

from django.urls import reverse

from apps.core.services.operation_result import OperationResult
from apps.dms.mapping.models import DmsProjectConfig
from apps.file_gate.bridge.services import dms_bridge_service
from apps.projects.models import Project


def get_settings_context(user, project: Project) -> dict:
    return dms_bridge_service.get_settings_context(user, project)


def save_settings(user, project: Project, data: dict) -> OperationResult:
    return dms_bridge_service.save_settings(user, project, data)


def precheck_sides(
    project: Project,
    *,
    hash_a: str,
    hash_b: str,
) -> OperationResult:
    return dms_bridge_service.precheck_match_sides(
        project, hash_a=hash_a, hash_b=hash_b
    )


def stamp_job(job, seal: dict) -> None:
    dms_bridge_service.stamp_match_job(job, seal)


def get_run_banner(project: Project) -> dict:
    """Info de bridge para el hub Ejecutar (sin hashes aún)."""
    config = (
        DmsProjectConfig.objects.select_related("file_gate_project")
        .filter(project_id=project.id)
        .first()
    )
    enabled = bool(config and config.file_gate_enabled)
    gate = config.file_gate_project if config else None
    require_a = bool(config.file_gate_require_a) if config else False
    require_b = bool(config.file_gate_require_b) if config else False
    sides = []
    if require_a:
        sides.append("A")
    if require_b:
        sides.append("B")
    return {
        "enabled": enabled,
        "gate_project_slug": gate.slug if gate else "",
        "require_a": require_a,
        "require_b": require_b,
        "sides_label": " y ".join(sides) if sides else "—",
        "settings_url": reverse(
            "file_match:bridge_hub", kwargs={"project_slug": project.slug}
        ),
        "max_age_days": (
            config.file_gate_max_age_days
            if config
            else dms_bridge_service.DEFAULT_MAX_AGE_DAYS
        ),
    }
