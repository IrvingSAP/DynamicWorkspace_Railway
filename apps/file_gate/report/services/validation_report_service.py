"""Informe y evidencia FILE GATE — Módulo 4 (validation_report.md).

Presenta evidencia de un job ya finalizado (M3): resumen, incidencias
ofuscables, descargas con TTL/roles y certificado ligero.

Sin migración: reutiliza DmsExecutionJob + gate_report.json / gate_issues.csv.
"""

from __future__ import annotations

import json
import logging

from django.urls import reverse
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import detection_service, storage_service
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.transform_execution.constants import DOWNLOAD_TTL
from apps.file_gate.run.services import validation_engine_service as engine
from apps.file_gate.run.services import validation_run_service as run_svc
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

CERTIFICATE_VERSION = "1.0"
REPORT_TTL = DOWNLOAD_TTL  # 7 días

FINAL_GATE_STATUSES = frozenset(
    {
        engine.STATUS_PASSED,
        engine.STATUS_PASSED_WITH_WARNINGS,
        engine.STATUS_FAILED,
        engine.STATUS_PARTIAL,
        engine.STATUS_ERROR,
    }
)

# Estados de job DMS que indican corrida terminada.
FINAL_JOB_STATUSES = frozenset(
    {
        DmsExecutionJob.STATUS_COMPLETED,
        DmsExecutionJob.STATUS_PARTIAL,
        DmsExecutionJob.STATUS_FAILED,
        DmsExecutionJob.STATUS_CANCELLED,
    }
)


# --------------------------------------------------------------------------- #
# Roles / permisos (validation_report.md § Roles)
# --------------------------------------------------------------------------- #

def resolve_role(user, project: Project) -> str | None:
    """PA / ED / GE / CO, o None si no tiene acceso."""
    membership = project_service.get_membership(user, project)
    if membership is not None:
        return membership.role
    # Visibilidad compañía (company_viewer) ≈ CO
    from apps.file_gate.projects.services import gate_project_service

    if gate_project_service.user_can_view(user, project):
        return ProjectMembership.ROLE_CO
    return None


def can_view_report(user, project: Project) -> bool:
    return resolve_role(user, project) is not None


def can_view_issues(user, project: Project) -> bool:
    """CO no ve tabla de incidencias (FG-I04)."""
    role = resolve_role(user, project)
    return role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def can_reveal_values(user, project: Project) -> bool:
    """O2/O3: solo PA/ED revelan valores en UI."""
    role = resolve_role(user, project)
    return role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def can_download_files(user, project: Project) -> bool:
    """I8: CO denegado para JSON/CSV."""
    role = resolve_role(user, project)
    return role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def can_view_certificate(user, project: Project) -> bool:
    return can_view_report(user, project)


# --------------------------------------------------------------------------- #
# Ofuscación
# --------------------------------------------------------------------------- #

def mask_value(raw) -> str:
    """O1 algoritmo MVP: ≤2 → **; si no, 2 primeros + ***."""
    text = "" if raw is None else str(raw)
    if not text:
        return "—"
    if len(text) <= 2:
        return "**"
    return text[:2] + "***"


def issues_for_ui(issues: list[dict], *, reveal: bool) -> list[dict]:
    out = []
    for issue in issues or []:
        row = dict(issue)
        raw = row.get("value")
        row["value_raw"] = "" if raw is None else str(raw)
        row["value_display"] = row["value_raw"] if reveal else mask_value(raw)
        out.append(row)
    return out


# --------------------------------------------------------------------------- #
# TTL
# --------------------------------------------------------------------------- #

def job_finished_at(job: DmsExecutionJob):
    return job.finished_at or job.created_at


def is_download_expired(job: DmsExecutionJob) -> bool:
    ref = job_finished_at(job)
    if ref is None:
        return True
    if timezone.is_naive(ref):
        ref = timezone.make_aware(ref, timezone.utc)
    return timezone.now() > ref + REPORT_TTL


def ttl_remaining_label(job: DmsExecutionJob) -> str:
    if is_download_expired(job):
        return "vencido"
    ref = job_finished_at(job)
    if ref is None:
        return "—"
    if timezone.is_naive(ref):
        ref = timezone.make_aware(ref, timezone.utc)
    remaining = (ref + REPORT_TTL) - timezone.now()
    days = max(0, remaining.days)
    if days <= 0:
        hours = max(1, int(remaining.total_seconds() // 3600))
        return f"{hours} h restantes"
    if days == 1:
        return "1 día restante"
    return f"{days} días restantes"


def is_job_final(job: DmsExecutionJob) -> bool:
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    status = gate.get("status") or ""
    if status in FINAL_GATE_STATUSES:
        return True
    return job.status in FINAL_JOB_STATUSES and job.status != DmsExecutionJob.STATUS_UPLOADED


# --------------------------------------------------------------------------- #
# processing_report del contrato usado en el job
# --------------------------------------------------------------------------- #

def get_processing_report_flags(job: DmsExecutionJob) -> dict:
    defaults = {
        "report_enabled": True,
        "include_summary": True,
        "include_row_errors": True,
        "formats": ["json", "csv"],
    }
    try:
        profile = job.version.source_profile
        source = source_persistence_service.profile_to_dict(profile)
        report = source.get("processing_report") or {}
    except Exception:
        logger.exception("get_processing_report_flags job=%s", job.id)
        return defaults

    formats = report.get("formats")
    if not isinstance(formats, list) or not formats:
        formats = defaults["formats"]
    formats = [str(f).lower() for f in formats]

    return {
        "report_enabled": report.get("report_enabled", True) is not False,
        "include_summary": report.get("include_summary", True) is not False,
        "include_row_errors": report.get("include_row_errors", True) is not False,
        "formats": formats,
    }


def _load_full_issues_from_storage(job: DmsExecutionJob) -> list[dict]:
    """Lee issues del JSON de storage si existe; si no, preview del job."""
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    preview = list(gate.get("issues_preview") or [])
    if not job.report_path:
        return preview
    try:
        path = storage_service.absolute_from_stored(job.report_path)
        if not path.is_file():
            return preview
        payload = json.loads(path.read_text(encoding="utf-8"))
        issues = payload.get("issues")
        if isinstance(issues, list):
            return issues
    except Exception:
        logger.exception("load issues from report job=%s", job.id)
    return preview


# --------------------------------------------------------------------------- #
# Vistas de contexto
# --------------------------------------------------------------------------- #

def build_report_view(user, project: Project, job: DmsExecutionJob) -> dict:
    """Contexto completo para la pantalla de evidencia."""
    base = run_svc.build_job_view(project, job)
    flags = get_processing_report_flags(job)
    expired = is_download_expired(job)
    role = resolve_role(user, project)
    can_issues = can_view_issues(user, project) and flags["include_row_errors"]
    can_dl = can_download_files(user, project) and not expired and flags["report_enabled"]
    can_reveal = can_reveal_values(user, project)

    issues_raw: list[dict] = []
    if can_issues:
        issues_raw = _load_full_issues_from_storage(job)[:200]
    issues_ui = issues_for_ui(issues_raw, reveal=False)

    downloads = {}
    if can_dl:
        formats = set(flags["formats"])
        if "json" in formats and flags["include_summary"]:
            downloads["report"] = reverse(
                "file_gate:run_download",
                kwargs={"project_slug": project.slug, "job_id": job.id, "kind": "report"},
            )
        if "csv" in formats and flags["include_row_errors"] and can_issues:
            downloads["errors"] = reverse(
                "file_gate:run_download",
                kwargs={"project_slug": project.slug, "job_id": job.id, "kind": "errors"},
            )

    executed_by = ""
    if job.executed_by_id:
        user_obj = job.executed_by
        executed_by = getattr(user_obj, "email", None) or getattr(user_obj, "username", "") or str(user_obj)

    return {
        **base,
        "role": role,
        "is_final": is_job_final(job),
        "is_expired": expired,
        "ttl_label": ttl_remaining_label(job),
        "report_flags": flags,
        "can_view_issues": can_issues,
        "can_reveal_values": can_reveal,
        "can_download": can_dl,
        "can_certificate": can_view_certificate(user, project),
        "issues": issues_ui,
        "issues_count": len(issues_ui),
        "downloads": downloads,
        "certificate_url": reverse(
            "file_gate:report_certificate",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
        "executed_by": executed_by,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "report_disabled_notice": not flags["report_enabled"],
    }


def build_certificate(user, project: Project, job: DmsExecutionJob) -> dict:
    """Certificado ligero (I3: versión usada en el job)."""
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    metrics = gate.get("metrics") or {}
    decision = gate.get("decision") or {}
    gate_status = gate.get("status") or job.status
    schema = gate.get("schema_snapshot") or {}

    executed_by = ""
    if job.executed_by_id:
        user_obj = job.executed_by
        executed_by = getattr(user_obj, "email", None) or getattr(user_obj, "username", "") or ""

    company_name = getattr(project.company, "name", "") or ""

    return {
        "certificate_version": CERTIFICATE_VERSION,
        "product": "FILE GATE",
        "company": company_name,
        "project_slug": project.slug,
        "project_name": project.name,
        "job_id": str(job.id),
        "filename": job.input_original_filename,
        "size_bytes": job.input_size_bytes or 0,
        "size_label": detection_service.human_size(job.input_size_bytes or 0),
        "content_hash": job.input_content_hash or "",
        "published_version": gate.get("published_version_number")
        or schema.get("version")
        or (job.version.version_number if job.version_id else None),
        "file_type_code": schema.get("file_type_code") or "",
        "fields_count": schema.get("fields_count"),
        "gate_status": gate_status,
        "gate_status_label": run_svc.GATE_STATUS_LABELS.get(gate_status, gate_status),
        "gate_tone": run_svc.GATE_STATUS_TONE.get(gate_status, "failed"),
        "is_success": gate_status in (engine.STATUS_PASSED, engine.STATUS_PASSED_WITH_WARNINGS),
        "is_partial": gate_status == engine.STATUS_PARTIAL,
        "is_error": gate_status == engine.STATUS_ERROR,
        "reason": decision.get("reason") or "",
        "message": decision.get("message") or job.error_message or "",
        "metrics": metrics,
        "executed_by": executed_by,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "is_expired": is_download_expired(job),
    }


def certificate_json_payload(cert: dict) -> dict:
    def _iso(dt):
        if dt is None:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    return {
        "certificate_version": cert["certificate_version"],
        "product": cert["product"],
        "company": cert["company"],
        "project": {"slug": cert["project_slug"], "name": cert["project_name"]},
        "job_id": cert["job_id"],
        "file": {
            "original_filename": cert["filename"],
            "size_bytes": cert["size_bytes"],
            "content_hash": f"sha256:{cert['content_hash']}" if cert["content_hash"] else "",
        },
        "published_version": cert["published_version"],
        "result": {
            "status": cert["gate_status"],
            "reason": cert["reason"],
            "message": cert["message"],
        },
        "metrics": {
            "rows_read": (cert.get("metrics") or {}).get("rows_read", 0),
            "rows_valid": (cert.get("metrics") or {}).get("rows_valid", 0),
            "rows_rejected": (cert.get("metrics") or {}).get("rows_rejected", 0),
            "reject_rate_percent": (cert.get("metrics") or {}).get("reject_rate_percent", 0),
        },
        "executed_by": cert["executed_by"],
        "started_at": _iso(cert.get("started_at")),
        "finished_at": _iso(cert.get("finished_at")),
    }


# --------------------------------------------------------------------------- #
# Autorización de descarga (refuerza M3)
# --------------------------------------------------------------------------- #

def authorize_download(user, project: Project, job: DmsExecutionJob, kind: str) -> OperationResult:
    if not can_download_files(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para descargar la evidencia de este job.",
        )
    if not is_job_final(job):
        return OperationResult.failure(
            "validation_form",
            "La validación aún no finalizó.",
        )
    if is_download_expired(job):
        return OperationResult.failure(
            "gone",
            "La evidencia expiró (TTL de 7 días). Los metadatos del job siguen disponibles.",
        )

    flags = get_processing_report_flags(job)
    if not flags["report_enabled"]:
        return OperationResult.failure(
            "validation_form",
            "El contrato deshabilitó el informe descargable.",
        )
    formats = set(flags["formats"])
    if kind == "report" and "json" not in formats:
        return OperationResult.failure(
            "validation_form",
            "El formato JSON no está habilitado en el contrato.",
        )
    if kind == "errors":
        if "csv" not in formats:
            return OperationResult.failure(
                "validation_form",
                "El formato CSV no está habilitado en el contrato.",
            )
        if not flags["include_row_errors"]:
            return OperationResult.failure(
                "validation_form",
                "El contrato no incluye detalle de incidencias por fila.",
            )

    stored, filename = run_svc.resolve_download(job, kind)
    if not stored:
        return OperationResult.failure("not_found", "Archivo de evidencia no encontrado.")
    path = storage_service.absolute_from_stored(stored)
    if not path.is_file():
        return OperationResult.failure(
            "gone",
            "El archivo de evidencia ya no está disponible.",
        )
    return OperationResult.success(
        payload={"stored": stored, "filename": filename, "path": path}
    )
