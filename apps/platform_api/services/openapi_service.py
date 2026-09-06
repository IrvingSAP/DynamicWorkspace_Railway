"""Índice de paths canónicos PLATFORM API (M9). YAML OpenAPI 3 aplazado."""

from __future__ import annotations

API_VERSION = "v1"
API_PREFIX = "/api/v1"

MSG_CATALOG = "Catálogo de paths canónicos."

AUTH_SCHEME = "Authorization: Bearer"
IDEMPOTENCY_HEADER = "Idempotency-Key"

# Un solo POST de ejecución; el atajo de pipeline no es otro producto.
CANONICAL_PATHS = [
    {
        "key": "run",
        "method": "POST",
        "path": "/api/v1/jobs/run",
        "module": "pa_jobs_run / pa_pipeline",
        "phase": "A/B",
        "implemented": True,
        "notes": "Un path de run para todos los kind. Pipeline: kind=file_pipeline.",
    },
    {
        "key": "job",
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}",
        "module": "pa_jobs_query",
        "phase": "A",
        "implemented": True,
        "notes": "Mismo path para todos los kinds. El id es el del historial de esa app (DMS, Match, Scout, Clean, Split/Merge o pipeline), no un id paralelo.",
    },
    {
        "key": "report",
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/report",
        "module": "pa_jobs_query",
        "phase": "A",
        "implemented": True,
        "notes": "Artifact firmado; no adivinar rutas de disco.",
    },
    {
        "key": "output",
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/output",
        "module": "pa_jobs_query",
        "phase": "A",
        "implemented": True,
        "notes": "Artifact firmado.",
    },
    {
        "key": "jobs",
        "method": "GET",
        "path": "/api/v1/jobs",
        "module": "pa_jobs_query",
        "phase": "B",
        "implemented": True,
        "notes": "Listado del tenant. Sin kind une las fuentes cableadas; con kind filtra esa app.",
    },
    {
        "key": "cancel",
        "method": "POST",
        "path": "/api/v1/jobs/{job_id}/cancel",
        "module": "pa_jobs_ops",
        "phase": "B",
        "implemented": True,
        "notes": "Obligatorio con wait=async.",
    },
    {
        "key": "pipeline_runs",
        "method": "POST",
        "path": "/api/v1/pipelines/{pipeline_id}/runs",
        "module": "pa_pipeline",
        "phase": "B",
        "implemented": True,
        "notes": "Atajo equivalente a POST /jobs/run con kind=file_pipeline.",
    },
    {
        "key": "ops_summary",
        "method": "GET",
        "path": "/api/v1/ops/summary",
        "module": "pa_audit",
        "phase": "C opcional",
        "implemented": False,
        "notes": "No en MVP. El tablero Pipeline cubre el pulso.",
    },
    {
        "key": "whoami",
        "method": "GET",
        "path": "/api/v1/whoami",
        "module": "pa_auth",
        "phase": "A",
        "implemented": True,
        "notes": "Identidad de máquina y scopes.",
    },
    {
        "key": "contract",
        "method": "GET",
        "path": "/api/v1/contract",
        "module": "pa_contract",
        "phase": "A",
        "implemented": True,
        "notes": "Catálogo de kinds, wait y envelope.",
    },
    {
        "key": "validate",
        "method": "POST",
        "path": "/api/v1/jobs/validate",
        "module": "pa_contract",
        "phase": "A",
        "implemented": True,
        "notes": "Valida metadatos; no ejecuta.",
    },
    {
        "key": "openapi",
        "method": "GET",
        "path": "/api/v1/openapi",
        "module": "pa_openapi",
        "phase": "A",
        "implemented": True,
        "notes": "Índice JSON. YAML OpenAPI 3 aplazado.",
    },
    {
        "key": "integration",
        "method": "GET",
        "path": "/api/v1/integration",
        "module": "pa_integration",
        "phase": "A",
        "implemented": True,
        "notes": "Inventario kind → runner, URLs UI y cableado.",
    },
]


def path_map() -> dict[str, str]:
    return {row["key"]: row["path"] for row in CANONICAL_PATHS}


def catalog() -> dict:
    return {
        "api_version": API_VERSION,
        "prefix": API_PREFIX,
        "yaml_deferred": True,
        "auth": AUTH_SCHEME,
        "idempotency_header": IDEMPOTENCY_HEADER,
        "error_contract": "pa_contract",
        "reusable_components_deferred": ["JobStatus", "ErrorItem"],
        "paths": list(CANONICAL_PATHS),
        "path_map": path_map(),
    }
