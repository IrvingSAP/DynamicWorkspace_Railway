from __future__ import annotations

import json
import uuid
from typing import Any

from apps.core.services.operation_result import OperationResult
from apps.platform_api.models import SCOPE_ARTIFACTS_DOWNLOAD, SCOPE_JOBS_RUN, SCOPE_PIPELINE_RUN

MSG_VALIDATION = "Revise los datos marcados; no se pudo validar el contrato."
MSG_UNKNOWN_KIND = "Kind no reconocido."
MSG_BAD_WAIT = "wait debe ser sync o async."
MSG_NEED_PROJECT = "Indique project_slug para un job suelto."
MSG_NEED_PIPELINE = "Indique pipeline_id para un pipeline."
MSG_MIXED_TARGET = "No mezcle project_slug de job suelto con pipeline_id."
MSG_NEED_FILE = "Falta el archivo requerido para este kind."
MSG_NEED_FILES = "Indique los archivos requeridos para este kind."
MSG_VALIDATED = "Metadatos del contrato válidos. Este endpoint no ejecuta el job."

KIND_GATE = "file_gate"
KIND_PIPE = "dms"
KIND_REVERSE = "reverse"
KIND_MATCH = "file_match"
KIND_SCOUT = "structure_scout"
KIND_CLEAN = "file_clean"
KIND_SPLIT = "file_split"
KIND_MERGE = "file_merge"
KIND_REPAIR = "file_repair"
KIND_PROFILER = "data_profiler"
KIND_PIPELINE = "file_pipeline"

WAIT_SYNC = "sync"
WAIT_ASYNC = "async"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

GATE_ACCEPTED = "accepted"
GATE_REJECTED = "rejected"

STEP_PENDING = "pending"
STEP_RUNNING = "running"
STEP_COMPLETED = "completed"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"

JOB_STATUSES = (
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
)
GATE_VERDICTS = (GATE_ACCEPTED, GATE_REJECTED)
STEP_STATUSES = (
    STEP_PENDING,
    STEP_RUNNING,
    STEP_COMPLETED,
    STEP_FAILED,
    STEP_SKIPPED,
)

KIND_DEFS: dict[str, dict[str, Any]] = {
    KIND_GATE: {
        "label": "File Gate",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_PIPE: {
        "label": "FilePipe",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_REVERSE: {
        "label": "Reverse Studio",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_MATCH: {
        "label": "File Match",
        "files": ["file_a", "file_b"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_SCOUT: {
        "label": "Structure Scout",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_CLEAN: {
        "label": "File Clean",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_SPLIT: {
        "label": "File Split",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_MERGE: {
        "label": "File Merge",
        "files": ["files"],
        "multi": True,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": True,
    },
    KIND_REPAIR: {
        "label": "File Repair",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": False,
    },
    KIND_PROFILER: {
        "label": "Data Profiler",
        "files": ["file"],
        "multi": False,
        "scope": SCOPE_JOBS_RUN,
        "default_wait": WAIT_SYNC,
        "mvp": False,
    },
    KIND_PIPELINE: {
        "label": "File Pipeline",
        "files": ["file"],
        "multi": True,
        "scope": SCOPE_PIPELINE_RUN,
        "default_wait": WAIT_ASYNC,
        "mvp": True,
    },
}

HTTP_BY_ERROR = {
    "invalid_token": 401,
    "insufficient_scope": 403,
    "company_inactive": 403,
    "validation_form": 400,
    "unpublished": 409,
    "not_found": 404,
    "rate_limited": 429,
    "idempotency_conflict": 409,
    "cancel_not_allowed": 409,
    "forbidden": 403,
}


def catalog() -> dict:
    kinds = []
    for code, meta in KIND_DEFS.items():
        kinds.append(
            {
                "kind": code,
                "label": meta["label"],
                "files": list(meta["files"]),
                "multi_file": bool(meta["multi"]),
                "scope": meta["scope"],
                "default_wait": meta["default_wait"],
                "mvp_phase_a": bool(meta["mvp"]),
            }
        )
    return {
        "wait": [WAIT_SYNC, WAIT_ASYNC],
        "job_status": list(JOB_STATUSES),
        "gate_verdict": list(GATE_VERDICTS),
        "step_status": list(STEP_STATUSES),
        "kinds": kinds,
        "envelope_fields": [
            "ok",
            "job_id",
            "kind",
            "project_slug",
            "pipeline_id",
            "version",
            "wait",
            "status",
            "summary",
            "errors",
            "artifacts",
            "content_hash",
            "links",
        ],
        "error_item_fields": ["row", "field", "code", "message"],
        "business_http": "Gate/Pipe de negocio: HTTP 200 con ok true/false; status de máquina completed. No usar accepted como status de pipeline.",
        "artifact_scope": SCOPE_ARTIFACTS_DOWNLOAD,
        "paths": path_map_from_openapi(),
        "integration_path": "/api/v1/integration",
    }


def path_map_from_openapi() -> dict:
    from apps.platform_api.services.openapi_service import path_map

    return path_map()


def error_item(*, row: int | None, field: str, code: str, message: str) -> dict:
    return {"row": row, "field": field, "code": code, "message": message}


def envelope(
    *,
    ok: bool,
    job_id: str | None,
    kind: str,
    status: str,
    wait: str = WAIT_SYNC,
    project_slug: str | None = None,
    pipeline_id: str | None = None,
    pipeline_run_id: str | None = None,
    version: str = "published",
    summary: dict | None = None,
    errors: list | None = None,
    artifacts: dict | None = None,
    content_hash: str | None = None,
    steps: list | None = None,
    extra: dict | None = None,
) -> dict:
    body = {
        "ok": ok,
        "job_id": job_id,
        "kind": kind,
        "project_slug": project_slug,
        "pipeline_id": pipeline_id,
        "version": version,
        "wait": wait,
        "status": status,
        "summary": summary or {},
        "errors": errors or [],
        "artifacts": artifacts or {},
        "content_hash": content_hash,
        "links": {"self": f"/api/v1/jobs/{job_id}" if job_id else None},
    }
    if pipeline_run_id:
        body["pipeline_run_id"] = pipeline_run_id
    if steps is not None:
        body["steps"] = steps
    if extra:
        body.update(extra)
    return body


def http_status_for(*, wait: str, status: str, protocol_error: str | None = None) -> int:
    if protocol_error:
        return HTTP_BY_ERROR.get(protocol_error, 400)
    if wait == WAIT_ASYNC and status in {STATUS_QUEUED, STATUS_RUNNING}:
        return 202
    return 200


def _posted_mapping(source) -> dict:
    if hasattr(source, "getlist"):
        data = {key: source.get(key) for key in source.keys()}
        if source.getlist("files") or source.getlist("files[]"):
            data["files"] = source.getlist("files") or source.getlist("files[]")
        return data
    if isinstance(source, dict):
        return dict(source)
    return {}


def posted_from_request(request) -> dict:
    content_type = (request.META.get("CONTENT_TYPE") or "").lower()
    if "application/json" in content_type:
        try:
            raw = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        posted = _posted_mapping(raw)
    else:
        posted = _posted_mapping(request.POST)
    posted["idempotency_key"] = (
        request.headers.get("Idempotency-Key")
        or posted.get("idempotency_key")
        or ""
    )
    posted["correlation_id"] = (
        request.headers.get("X-Correlation-Id")
        or posted.get("correlation_id")
        or ""
    )
    from apps.platform_api.services import job_audit_service

    posted["client_ip"] = job_audit_service.client_ip_from_meta(request.META)
    posted["user_agent"] = job_audit_service.user_agent_from_meta(request.META)
    files_map: dict[str, Any] = {}
    if getattr(request, "FILES", None):
        files_map = {key: request.FILES.getlist(key) for key in request.FILES}
        if "files[]" in files_map and "files" not in files_map:
            files_map["files"] = files_map["files[]"]
    posted["_files"] = files_map
    return posted


def parse_run_request(posted: dict, *, require_files: bool = False) -> OperationResult:
    errors: dict[str, list[str]] = {}
    kind = str(posted.get("kind") or "").strip()
    mode = str(posted.get("mode") or "").strip().lower()
    if mode == "pipeline" and not kind:
        kind = KIND_PIPELINE
    if kind not in KIND_DEFS:
        errors["kind"] = [MSG_UNKNOWN_KIND]
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    meta = KIND_DEFS[kind]
    wait_raw = str(posted.get("wait") or meta["default_wait"]).strip().lower()
    if wait_raw not in {WAIT_SYNC, WAIT_ASYNC}:
        errors["wait"] = [MSG_BAD_WAIT]
        wait_raw = meta["default_wait"]

    version = str(posted.get("version") or "published").strip() or "published"
    project_slug = str(posted.get("project_slug") or posted.get("project_id") or "").strip()
    pipeline_id = str(posted.get("pipeline_id") or "").strip()
    if kind == KIND_PIPELINE:
        if not pipeline_id:
            errors["pipeline_id"] = [MSG_NEED_PIPELINE]
        if project_slug:
            errors["project_slug"] = [MSG_MIXED_TARGET]
    else:
        if not project_slug:
            errors["project_slug"] = [MSG_NEED_PROJECT]
        if pipeline_id:
            errors["pipeline_id"] = [MSG_MIXED_TARGET]

    dry_raw = posted.get("dry_run")
    dry_run = str(dry_raw).lower() in {"1", "true", "yes", "on"} if dry_raw not in (None, "") else False

    file_slots = list(meta["files"])
    files_in = posted.get("_files") or {}
    if require_files:
        if meta["multi"] and kind == KIND_MERGE:
            items = files_in.get("files") or files_in.get("files[]") or []
            if len(items) < 2:
                errors["files"] = [MSG_NEED_FILES]
        elif kind == KIND_PIPELINE:
            has_any = bool(files_in.get("file") or files_in.get("files") or files_in.get("files[]"))
            if not has_any:
                errors["file"] = [MSG_NEED_FILE]
        else:
            for slot in file_slots:
                if not files_in.get(slot):
                    errors[slot] = [MSG_NEED_FILE]

    retry_raw = str(posted.get("retry_of_job_id") or posted.get("retry_of_run_id") or "").strip()
    retry_of_job_id = retry_raw or None
    if retry_raw:
        try:
            uuid.UUID(retry_raw)
        except ValueError:
            errors["retry_of_job_id"] = ["Indique un job_id válido para el reintento."]
            retry_of_job_id = None

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    parsed = {
        "kind": kind,
        "wait": wait_raw,
        "version": version,
        "project_slug": project_slug or None,
        "pipeline_id": pipeline_id or None,
        "dry_run": dry_run,
        "retry_of_job_id": retry_of_job_id,
        "idempotency_key": str(posted.get("idempotency_key") or "").strip()[:128],
        "correlation_id": str(posted.get("correlation_id") or "").strip()[:64],
        "client_ip": str(posted.get("client_ip") or "").strip()[:45],
        "user_agent": str(posted.get("user_agent") or "").strip()[:300],
        "files_required": file_slots,
        "multi_file": bool(meta["multi"]),
        "scope": meta["scope"],
        "default_http_status": http_status_for(
            wait=wait_raw,
            status=STATUS_QUEUED if wait_raw == WAIT_ASYNC else STATUS_COMPLETED,
        ),
    }
    return OperationResult.success(MSG_VALIDATED, parsed=parsed)


def validate_posted(posted: dict, *, require_files: bool = False) -> OperationResult:
    return parse_run_request(posted, require_files=require_files)
