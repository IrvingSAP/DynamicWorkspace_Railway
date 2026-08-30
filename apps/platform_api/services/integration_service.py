"""Inventario transversal: kind → runner, URLs UI y cableado HTTP."""

from __future__ import annotations

from django.apps import apps

from apps.platform_api.services import contract_service, job_run_service, openapi_service
from apps.projects.models import Project

MSG_CATALOG = "Catálogo de integración: runners por kind."

PRODUCT_CODE = "PLATFORM_API"
DJANGO_APP = "apps.platform_api"
HTTP_PREFIX = "/api/v1/"
UI_CLIENTS = "/app/platform-api/clientes/"
UI_INTEGRATION = "/app/platform-api/integracion/"
UF_SIDEBAR = False
EXCLUDED_KINDS = ("workspace",)

API_RUN = "/api/v1/jobs/run"
API_JOB = "/api/v1/jobs/{job_id}"
API_PIPELINE_RUNS = "/api/v1/pipelines/{pipeline_id}/runs"

KIND_ROWS: tuple[dict, ...] = (
    {
        "kind": contract_service.KIND_GATE,
        "label": "File Gate",
        "django_app": "apps.file_gate",
        "project_kind": Project.KIND_FILE_GATE,
        "runner": "apps.file_gate.run.services.validation_run_service.validate_and_run",
        "api_entry": "apps.platform_api.services.job_run_service._run_sync",
        "phase": "A",
        "ui_execute": "/app/file-gate/proyectos/{project_slug}/validar/ejecutar/",
        "ui_history": "/app/file-gate/proyectos/{project_slug}/historial/",
        "job_id_same": True,
        "notes": "Mismo job_id que el historial Gate.",
    },
    {
        "kind": contract_service.KIND_PIPE,
        "label": "FilePipe",
        "django_app": "apps.dms",
        "project_kind": Project.KIND_DMS,
        "runner": "apps.dms.transform_execution.services.execution_service.run_full_job",
        "api_entry": "apps.platform_api.services.job_run_service._run_sync",
        "phase": "A",
        "ui_execute": "/app/filepipe/proyectos/{project_slug}/ejecutar/",
        "ui_history": "/app/filepipe/proyectos/{project_slug}/ejecutar/historial/",
        "job_id_same": True,
        "notes": "Intake + run_full_job / dry_run_job.",
    },
    {
        "kind": contract_service.KIND_REVERSE,
        "label": "Reverse Studio",
        "django_app": "apps.reverse_studio",
        "project_kind": Project.KIND_REVERSE,
        "runner": "apps.dms.transform_execution.services.execution_service.run_full_job",
        "api_entry": "apps.platform_api.services.job_run_service._run_sync",
        "phase": "B",
        "ui_execute": "/app/reverse-studio/proyectos/{project_slug}/generar/",
        "ui_history": "/app/reverse-studio/proyectos/{project_slug}/historial/",
        "job_id_same": True,
        "notes": "Reusa el runner DMS. Cableado en POST /jobs/run (Fase B).",
    },
    {
        "kind": contract_service.KIND_MATCH,
        "label": "File Match",
        "django_app": "apps.file_match",
        "project_kind": Project.KIND_FILE_MATCH,
        "runner": "apps.file_match.run.services.match_run_service.match_and_run",
        "api_entry": "apps.platform_api.services.job_run_service._run_match",
        "phase": "B",
        "ui_execute": "/app/file-match/proyectos/{project_slug}/ejecutar/ejecutar/",
        "ui_history": "/app/file-match/proyectos/{project_slug}/historial/",
        "job_id_same": True,
        "notes": "Dos archivos (file_a, file_b). Cableado en POST /jobs/run (Fase B). Solo wait=sync.",
    },
    {
        "kind": contract_service.KIND_SCOUT,
        "label": "Structure Scout",
        "django_app": "apps.structure_scout",
        "project_kind": Project.KIND_STRUCTURE_SCOUT,
        "runner": "apps.structure_scout.detect.services.detect_pattern_service.rerun_detection",
        "api_entry": "apps.platform_api.services.job_run_service._run_scout",
        "phase": "B",
        "ui_execute": "/app/structure-scout/proyectos/{project_slug}/detectar/",
        "ui_history": "/app/structure-scout/proyectos/{project_slug}/historial/",
        "job_id_same": False,
        "notes": "Sube muestra y reejecuta detección. Cableado en POST /jobs/run (Fase B). Solo wait=sync. job_id = detección, no job productivo.",
    },
    {
        "kind": contract_service.KIND_CLEAN,
        "label": "File Clean",
        "django_app": "apps.file_clean",
        "project_kind": Project.KIND_FILE_CLEAN,
        "runner": "apps.file_clean.run.services.clean_run_service.run_clean_job",
        "api_entry": "apps.platform_api.services.job_run_service._run_clean",
        "phase": "C",
        "ui_execute": "/app/file-clean/proyectos/{project_slug}/ejecutar/ejecutar/",
        "ui_history": "/app/file-clean/proyectos/{project_slug}/historial/",
        "job_id_same": True,
        "notes": "Cableado en POST /jobs/run (Fase C). Mismo runner que la UI. Solo wait=sync. Admite dry_run.",
    },
    {
        "kind": contract_service.KIND_SPLIT,
        "label": "File Split",
        "django_app": "apps.file_split_merge",
        "project_kind": Project.KIND_FILE_SPLIT_MERGE,
        "runner": "apps.file_split_merge.run.services.sm_run_service.run_sm_job",
        "api_entry": "apps.platform_api.services.job_run_service._run_sm",
        "phase": "C",
        "ui_execute": "/app/file-split-merge/proyectos/{project_slug}/ejecutar/ejecutar/",
        "ui_history": "/app/file-split-merge/proyectos/{project_slug}/historial/",
        "job_id_same": True,
        "notes": "Cableado en POST /jobs/run (Fase C). Un archivo. Solo wait=sync. Operación publicada debe ser split.",
    },
    {
        "kind": contract_service.KIND_MERGE,
        "label": "File Merge",
        "django_app": "apps.file_split_merge",
        "project_kind": Project.KIND_FILE_SPLIT_MERGE,
        "runner": "apps.file_split_merge.run.services.sm_run_service.run_sm_job",
        "api_entry": "apps.platform_api.services.job_run_service._run_sm",
        "phase": "C",
        "ui_execute": "/app/file-split-merge/proyectos/{project_slug}/ejecutar/ejecutar/",
        "ui_history": "/app/file-split-merge/proyectos/{project_slug}/historial/",
        "job_id_same": True,
        "notes": "Cableado en POST /jobs/run (Fase C). Slot files (mín. 2). Solo wait=sync. Operación publicada debe ser merge.",
    },
    {
        "kind": contract_service.KIND_REPAIR,
        "label": "File Repair",
        "django_app": "apps.file_repair",
        "project_kind": "",
        "runner": "",
        "api_entry": "",
        "phase": "C",
        "ui_execute": "",
        "ui_history": "",
        "job_id_same": True,
        "notes": "App no instalada. Kind reservado en el contrato.",
    },
    {
        "kind": contract_service.KIND_PROFILER,
        "label": "Data Profiler",
        "django_app": "apps.data_profiler",
        "project_kind": "",
        "runner": "",
        "api_entry": "",
        "phase": "C",
        "ui_execute": "",
        "ui_history": "",
        "job_id_same": True,
        "notes": "App no instalada. Kind reservado en el contrato.",
    },
    {
        "kind": contract_service.KIND_PIPELINE,
        "label": "File Pipeline",
        "django_app": "apps.file_pipeline",
        "project_kind": "",
        "runner": "apps.file_pipeline.services.pipeline_run_service.start_run",
        "api_entry": "apps.platform_api.services.job_run_service._run_pipeline",
        "phase": "B",
        "ui_execute": "/app/file-pipeline/pipelines/{pipeline_slug}/ejecutar/",
        "ui_history": "/app/file-pipeline/pipelines/{pipeline_slug}/historial/",
        "job_id_same": True,
        "notes": "Delega al orquestador. trigger_source=api. Mismo pipeline_run_id.",
    },
)

UI_API_MAP = (
    {
        "ui": "Ejecutar proyecto publicado",
        "api": "POST /api/v1/jobs/run + kind + project_slug",
    },
    {
        "ui": "Ejecutar pipeline publicado",
        "api": "kind=file_pipeline o POST /api/v1/pipelines/{pipeline_id}/runs",
    },
    {
        "ui": "Historial de la app",
        "api": "Mismo job_id (GET /api/v1/jobs/{job_id})",
    },
    {
        "ui": "Detalle / auditoría pipeline",
        "api": "Mismo pipeline_run_id",
    },
    {
        "ui": "Tablero Pipeline",
        "api": "Cuenta corridas con trigger_source=api",
    },
    {
        "ui": "GE en proyecto",
        "api": "Scope run + membresía/servicio del proyecto destino",
    },
)


def _wired(kind: str) -> bool:
    return kind in job_run_service.MVP_KINDS


def identity() -> dict:
    return {
        "product_code": PRODUCT_CODE,
        "django_app": DJANGO_APP,
        "http_prefix": HTTP_PREFIX,
        "uf_sidebar": UF_SIDEBAR,
        "ui_clients": UI_CLIENTS,
        "ui_integration": UI_INTEGRATION,
        "whoami": "/api/v1/whoami",
        "run_path": API_RUN,
        "excluded_kinds": list(EXCLUDED_KINDS),
    }


def runners() -> list[dict]:
    rows = []
    for item in KIND_ROWS:
        kind = item["kind"]
        django_app = item["django_app"]
        rows.append(
            {
                **item,
                "wired": _wired(kind),
                "app_installed": bool(django_app) and apps.is_installed(django_app),
                "mvp": kind in job_run_service.MVP_KINDS,
            }
        )
    return rows


def catalog() -> dict:
    rows = runners()
    return {
        "identity": identity(),
        "reuses": [
            "Runners de cada app (validate_and_run, run_full_job, start_run).",
            "Orquestador File Pipeline.",
            "Company + flags; storage y TTL de jobs existentes.",
        ],
        "does_not_reuse": [
            "Parsers, reglas y diseñadores.",
            "Un segundo motor de cadena.",
            "Historial paralelo no enlazado.",
            "Tenant propio.",
        ],
        "runners": rows,
        "wired_kinds": [row["kind"] for row in rows if row["wired"]],
        "ui_api_map": list(UI_API_MAP),
        "watch_scheduler": "Mismo runner; trigger_source distinto (ui / api / watch / scheduler).",
        "archive": (
            "Custodia de job_id y pipeline_run_id (hash entrada → hash salida). "
            "No bloquea el MVP; File Archive no está en INSTALLED_APPS."
        ),
        "single_run_path": API_RUN,
        "pipeline_alias": API_PIPELINE_RUNS,
        "job_query": API_JOB,
        "paths": openapi_service.path_map(),
    }
