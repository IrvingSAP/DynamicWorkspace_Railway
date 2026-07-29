"""Contexto UI y helpers del Módulo 5 — Generar archivo de envío."""

from __future__ import annotations

from django.urls import reverse

from apps.dms.file_intake.services import (
    file_intake_persistence_service,
    file_intake_service,
)
from apps.dms.transform_execution.services import execution_service, execution_ui_service
from apps.projects.models import ProjectMembership

DOWNLOAD_URL_NAMES = {
    "output": "run_download_output",
    "report": "run_download_report",
    "errors": "run_download_errors",
}


def user_can_download(user, project) -> bool:
    """PA / ED / GE: sí. CO y visitante compañía: no (GEN2 / RS3)."""
    return execution_service.user_can_execute(user, project)


def remapped_execute_message(message: str) -> str:
    mapping = {
        "No tiene permiso para ejecutar transformaciones de este proyecto.": (
            "No tiene permiso para generar archivos de envío en este proyecto."
        ),
        "El job no tiene archivo de entrada subido.": (
            "El job no tiene una planilla subida."
        ),
        "Este job ya fue ejecutado o está en ejecución.": (
            "Esta generación ya se ejecutó o está en curso."
        ),
        "Ocurrió un error al previsualizar. Si persiste, contacte al administrador.": (
            "Ocurrió un error al previsualizar la generación. Si persiste, contacte al administrador."
        ),
        "Ocurrió un error al ejecutar. Si persiste, contacte al administrador.": (
            "Ocurrió un error al generar el archivo. Si persiste, contacte al administrador."
        ),
        "Error inesperado al ejecutar.": "Error inesperado al generar.",
    }
    if message.startswith("Transformación finalizada:"):
        return message.replace("Transformación finalizada:", "Archivo de envío generado:", 1)
    return mapping.get(message, message)


def remapped_upload_message(message: str) -> str:
    if message == "Archivo de producción subido correctamente.":
        return "Planilla subida correctamente."
    return message


def get_hub_context(user, project, membership) -> dict:
    intake = file_intake_service.get_hub_context(project, membership)
    intake["can_upload_sample"] = False
    intake["can_upload_production"] = (
        file_intake_persistence_service.user_can_upload_production(user, project)
    )

    exec_ctx = execution_ui_service.get_hub_context(
        project,
        membership,
        download_url_namespace="reverse_studio",
        download_url_names=DOWNLOAD_URL_NAMES,
        force_bridge_disabled=False,
    )
    if exec_ctx.get("bridge_enabled"):
        exec_ctx["bridge_settings_url"] = reverse(
            "reverse_studio:bridge_hub",
            kwargs={"project_slug": project.slug},
        )

    can_download = user_can_download(user, project)
    if not can_download:
        for row in exec_ctx.get("history_jobs") or []:
            row["downloads"] = {}

    role = membership.role if membership else None
    return {
        **intake,
        **exec_ctx,
        "can_execute": execution_service.user_can_execute(user, project),
        "can_download": can_download,
        "is_consulta": role == ProjectMembership.ROLE_CO,
        "production_upload_url": reverse(
            "reverse_studio:run_production_upload",
            kwargs={"project_slug": project.slug},
        ),
        "preview_url_template": reverse(
            "reverse_studio:run_preview",
            kwargs={
                "project_slug": project.slug,
                "job_id": "00000000-0000-0000-0000-000000000000",
            },
        ),
        "run_url_template": reverse(
            "reverse_studio:run_generate",
            kwargs={
                "project_slug": project.slug,
                "job_id": "00000000-0000-0000-0000-000000000000",
            },
        ),
        "history_url": reverse(
            "reverse_studio:history_hub",
            kwargs={"project_slug": project.slug},
        ),
        "bridge_hub_url": reverse(
            "reverse_studio:bridge_hub",
            kwargs={"project_slug": project.slug},
        ),
        "publish_hub_url": reverse(
            "reverse_studio:publish_hub",
            kwargs={"project_slug": project.slug},
        ),
    }
