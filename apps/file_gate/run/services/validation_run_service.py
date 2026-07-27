"""Orquestación de ejecución FILE GATE — Módulo 3 (validation_run.md).

Reutiliza:
- DmsExecutionJob (persistencia de la corrida; sin migración nueva).
- Parsers/validadores DMS vía validation_engine_service.
- Storage tenant-safe e intake DMS (extensiones, tamaño, nombre seguro).

Persistencia del veredicto del gate: DmsExecutionJob.input_suggestions["gate_result"].
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.constants import PRODUCTION_PREVIEW_MAX_BYTES
from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import (
    detection_service,
    file_intake_persistence_service,
    storage_service,
)
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.file_gate.policy.services import gate_policy_service
from apps.file_gate.run.services import validation_engine_service as engine
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

# Límite de tamaño para ejecución síncrona MVP (alineado a intake de producción).
RUN_MAX_BYTES = PRODUCTION_PREVIEW_MAX_BYTES  # 50 MB

# Mapeo estado de gate -> estado persistido en DmsExecutionJob.
_STATUS_TO_JOB = {
    engine.STATUS_PASSED: DmsExecutionJob.STATUS_COMPLETED,
    engine.STATUS_PASSED_WITH_WARNINGS: DmsExecutionJob.STATUS_COMPLETED,
    engine.STATUS_FAILED: DmsExecutionJob.STATUS_FAILED,
    engine.STATUS_PARTIAL: DmsExecutionJob.STATUS_PARTIAL,
    engine.STATUS_ERROR: DmsExecutionJob.STATUS_FAILED,
}

GATE_STATUS_LABELS = {
    engine.STATUS_PASSED: "Aprobado",
    engine.STATUS_PASSED_WITH_WARNINGS: "Aprobado con advertencias",
    engine.STATUS_FAILED: "Rechazado",
    engine.STATUS_PARTIAL: "Parcial",
    engine.STATUS_ERROR: "Error técnico",
}

GATE_STATUS_TONE = {
    engine.STATUS_PASSED: "passed",
    engine.STATUS_PASSED_WITH_WARNINGS: "passed",
    engine.STATUS_FAILED: "failed",
    engine.STATUS_PARTIAL: "partial",
    engine.STATUS_ERROR: "failed",
}


# --------------------------------------------------------------------------- #
# Permisos y resolución de versión publicada
# --------------------------------------------------------------------------- #

def user_can_execute(user, project: Project) -> bool:
    """V2: ejecutar requiere PA, ED o GE."""
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def get_published_version(project: Project) -> DmsMappingVersion | None:
    return file_intake_persistence_service.get_published_version(project)


def _published_source(published: DmsMappingVersion) -> dict:
    source = source_persistence_service.profile_to_dict(published.source_profile)
    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list as normalize_source_fields,
    )

    source["fields"] = normalize_source_fields(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    return source


def _published_policy(source: dict) -> dict:
    config = source.get("config") or {}
    return gate_policy_service.normalize_gate_policy(config.get("gate_policy"), source=source)


def allowed_extensions_for_published(published: DmsMappingVersion | None) -> list[str]:
    if published is None:
        return []
    try:
        code = (published.source_profile.file_type_code or "").strip()
        from apps.dms.models import SourceFileType

        match = SourceFileType.objects.filter(code=code, is_active=True).first()
        if match and match.extensions:
            return [str(ext).lower() for ext in match.extensions]
    except Exception:
        logger.exception("allowed_extensions_for_published failed")
    return []


# --------------------------------------------------------------------------- #
# Contexto de pantallas
# --------------------------------------------------------------------------- #

def get_run_context(user, project: Project) -> dict:
    published = get_published_version(project)
    can_execute = user_can_execute(user, project)
    ctx: dict = {
        "has_published_version": published is not None,
        "can_execute": can_execute,
        "published_version_number": published.version_number if published else None,
        "file_type_label": "—",
        "file_type_code": "",
        "threshold_label": "—",
        "collection_label": "—",
        "max_errors": None,
        "allowed_extensions": [],
        "allowed_extensions_label": "—",
        "max_size_label": detection_service.human_size(RUN_MAX_BYTES),
        "fields_count": 0,
        "recent_jobs": [],
    }

    if published is not None:
        source = _published_source(published)
        policy = _published_policy(source)
        code = (source.get("file_type_code") or "").strip()
        allowed = allowed_extensions_for_published(published)
        ctx.update(
            {
                "file_type_code": code,
                "file_type_label": source_persistence_service.file_type_label(code),
                "threshold_label": gate_policy_service.threshold_summary(policy),
                "collection_label": gate_policy_service.collection_summary(policy),
                "max_errors": policy.get("max_errors"),
                "allowed_extensions": allowed,
                "allowed_extensions_label": ", ".join(allowed) if allowed else "—",
                "fields_count": len(source.get("fields") or []),
            }
        )

    ctx["recent_jobs"] = list_recent(project, limit=8)
    return ctx


def _job_status_summary(job: DmsExecutionJob) -> dict:
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    gate_status = gate.get("status") or job.status
    return {
        "job": job,
        "id": str(job.id),
        "filename": job.input_original_filename,
        "gate_status": gate_status,
        "gate_status_label": GATE_STATUS_LABELS.get(gate_status, gate_status),
        "gate_tone": GATE_STATUS_TONE.get(gate_status, "failed"),
        "reject_rate": (gate.get("metrics") or {}).get("reject_rate_percent"),
        "rows_read": job.rows_read,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def list_recent(project: Project, *, limit: int = 8) -> list[dict]:
    jobs = (
        DmsExecutionJob.objects.filter(project=project)
        .exclude(status=DmsExecutionJob.STATUS_UPLOADED)
        .select_related("executed_by")
        .order_by("-created_at")[:limit]
    )
    return [_job_status_summary(job) for job in jobs]


def get_job(project: Project, job_id) -> DmsExecutionJob | None:
    return (
        DmsExecutionJob.objects.select_related("version", "version__source_profile", "executed_by")
        .filter(project=project, id=job_id)
        .first()
    )


def build_job_view(project: Project, job: DmsExecutionJob) -> dict:
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    gate_status = gate.get("status") or job.status
    metrics = gate.get("metrics") or {}
    decision = gate.get("decision") or {}
    issues = gate.get("issues_preview") or []
    return {
        "job": job,
        "id": str(job.id),
        "filename": job.input_original_filename,
        "size_label": detection_service.human_size(job.input_size_bytes or 0),
        "content_hash": job.input_content_hash,
        "published_version_number": gate.get("published_version_number")
        or (job.version.version_number if job.version_id else None),
        "gate_status": gate_status,
        "gate_status_label": GATE_STATUS_LABELS.get(gate_status, gate_status),
        "gate_tone": GATE_STATUS_TONE.get(gate_status, "failed"),
        "is_success": gate_status in (engine.STATUS_PASSED, engine.STATUS_PASSED_WITH_WARNINGS),
        "is_partial": gate_status == engine.STATUS_PARTIAL,
        "metrics": metrics,
        "decision": decision,
        "policy_snapshot": gate.get("policy_snapshot") or {},
        "schema_snapshot": gate.get("schema_snapshot") or {},
        "issues": issues,
        "error_message": job.error_message,
        "downloads": build_download_links(project.slug, job) if job.report_path else {},
    }


def build_download_links(project_slug: str, job: DmsExecutionJob) -> dict:
    links = {}
    for kind in ("report", "errors"):
        links[kind] = reverse(
            "file_gate:run_download",
            kwargs={"project_slug": project_slug, "job_id": job.id, "kind": kind},
        )
    return links


# --------------------------------------------------------------------------- #
# Ejecución
# --------------------------------------------------------------------------- #

def _validate_upload(uploaded_file, *, allowed_exts: list[str]) -> OperationResult | None:
    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            "Seleccione un archivo para validar.",
            errors={"file": ["Seleccione un archivo."]},
        )
    name = getattr(uploaded_file, "name", "") or ""
    ext = detection_service.extension_of(name)
    if allowed_exts and (not ext or ext not in allowed_exts):
        return OperationResult.failure(
            "validation_form",
            "La extensión del archivo no coincide con el contrato publicado.",
            errors={
                "file": [
                    f"Extensión «{ext or 'sin extensión'}» no permitida. "
                    f"Permitidas: {', '.join(allowed_exts)}."
                ]
            },
        )
    size = getattr(uploaded_file, "size", None)
    if size is not None and size == 0:
        return OperationResult.failure(
            "validation_form",
            "El archivo está vacío.",
            errors={"file": ["El archivo no puede estar vacío."]},
        )
    if size is not None and size > RUN_MAX_BYTES:
        return OperationResult.failure(
            "validation_form",
            f"El archivo supera el límite de {detection_service.human_size(RUN_MAX_BYTES)}.",
            errors={
                "file": [
                    f"Tamaño máximo permitido: {detection_service.human_size(RUN_MAX_BYTES)}."
                ]
            },
        )
    return None


def _schema_snapshot(source: dict, published: DmsMappingVersion) -> dict:
    return {
        "version": published.version_number,
        "file_type_code": source.get("file_type_code") or "",
        "fields_count": len(source.get("fields") or []),
    }


def _write_reports(project: Project, job: DmsExecutionJob, gate: dict) -> str:
    """Escribe gate_report.json + gate_issues.csv. Devuelve path relativo del JSON."""
    reports_dir = storage_service.job_reports_dir(project.company_id, project.id, job.id)
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "job_id": str(job.id),
        "status": gate.get("status"),
        "published_version": gate.get("published_version_number"),
        "file": {
            "original_filename": job.input_original_filename,
            "size_bytes": job.input_size_bytes,
            "content_hash": job.input_content_hash,
        },
        "metrics": gate.get("metrics") or {},
        "policy_snapshot": gate.get("policy_snapshot") or {},
        "schema_snapshot": gate.get("schema_snapshot") or {},
        "decision": gate.get("decision") or {},
        "issues": gate.get("issues") or [],
    }
    json_abs = reports_dir / "gate_report.json"
    json_abs.write_text(
        json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["line", "field", "severity", "code", "message", "value"])
    for issue in gate.get("issues") or []:
        writer.writerow(
            [
                issue.get("line", ""),
                issue.get("field", ""),
                issue.get("severity", ""),
                issue.get("code", ""),
                issue.get("message", ""),
                issue.get("value", ""),
            ]
        )
    csv_abs = reports_dir / "gate_issues.csv"
    csv_abs.write_text(buffer.getvalue(), encoding="utf-8")

    return storage_service.relative_to_media(json_abs)


@transaction.atomic
def validate_and_run(user, project: Project, uploaded_file) -> OperationResult:
    """Sube el archivo, ejecuta la validación síncrona y persiste el job."""
    if project.project_kind != Project.KIND_FILE_GATE:
        return OperationResult.failure("forbidden", "Este proyecto no es de tipo FILE GATE.")
    if not user_can_execute(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para validar archivos en este proyecto.",
        )

    published = get_published_version(project)
    if published is None:
        return OperationResult.failure(
            "validation_form",
            "Publique el contrato antes de validar.",
            errors={"version": ["Se requiere una versión publicada."]},
        )

    allowed = allowed_extensions_for_published(published)
    invalid = _validate_upload(uploaded_file, allowed_exts=allowed)
    if invalid:
        return invalid

    job_id = uuid.uuid4()
    dest = storage_service.job_input_dir(project.company_id, project.id, job_id)
    try:
        stored_path, size_bytes, content_hash = storage_service.store_upload(
            uploaded_file, dest, prefix_uuid=str(job_id)
        )
    except Exception:
        logger.exception("validate_and_run store failed project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    if size_bytes == 0:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            "El archivo está vacío.",
            errors={"file": ["El archivo no puede estar vacío."]},
        )

    job = DmsExecutionJob.objects.create(
        id=job_id,
        project=project,
        version=published,
        job_type=DmsExecutionJob.JOB_FULL,
        status=DmsExecutionJob.STATUS_RUNNING,
        input_original_filename=storage_service.sanitize_filename(
            getattr(uploaded_file, "name", "file")
        ),
        input_stored_path=stored_path,
        input_size_bytes=size_bytes,
        input_content_hash=content_hash,
        input_mime_type=getattr(uploaded_file, "content_type", "") or "",
        executed_by=user,
        started_at=timezone.now(),
    )

    source = _published_source(published)
    policy = _published_policy(source)
    path = storage_service.absolute_from_stored(stored_path)

    try:
        result = engine.run_validation(path, source, policy)
    except engine.source_parser_service.ParseError as exc:
        result = engine.build_fatal_result(str(exc))
    except Exception:
        logger.exception("validate_and_run engine failed job=%s", job_id)
        _finish_error(job, "Ocurrió un error técnico al validar el archivo.")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al validar. Si persiste, contacte al administrador.",
        )

    gate = {
        "status": result.status,
        "published_version_number": published.version_number,
        "metrics": result.metrics,
        "policy_snapshot": policy,
        "schema_snapshot": _schema_snapshot(source, published),
        "decision": {
            "reason": result.decision_reason,
            "message": result.decision_message,
        },
        "issues": result.issues,
        "issues_preview": result.issues_preview,
    }

    try:
        report_rel = _write_reports(project, job, gate)
    except Exception:
        logger.exception("validate_and_run report failed job=%s", job_id)
        report_rel = ""

    metrics = result.metrics
    job.status = _STATUS_TO_JOB.get(result.status, DmsExecutionJob.STATUS_FAILED)
    job.rows_read = metrics.get("rows_read") or 0
    job.rows_ok = metrics.get("rows_valid") or 0
    job.rows_rejected = metrics.get("rows_rejected") or 0
    job.report_path = report_rel
    job.finished_at = timezone.now()
    # Guardar preview (no la lista completa) en el JSON del job.
    gate_persist = dict(gate)
    gate_persist.pop("issues", None)
    job.input_suggestions = {"gate_result": gate_persist}
    if result.decision_reason == engine.REASON_FATAL:
        job.error_message = result.decision_message
    job.save()
    project.save(update_fields=["updated_at"])

    return OperationResult.success(
        user_message=_result_user_message(result),
        payload={"job": job, "job_id": str(job.id), "gate_status": result.status},
    )


def _finish_error(job: DmsExecutionJob, message: str) -> None:
    job.status = DmsExecutionJob.STATUS_FAILED
    job.error_message = message
    job.finished_at = timezone.now()
    job.input_suggestions = {"gate_result": {"status": engine.STATUS_ERROR}}
    job.save(
        update_fields=[
            "status",
            "error_message",
            "finished_at",
            "input_suggestions",
            "updated_at",
        ]
    )


def _result_user_message(result: engine.GateResult) -> str:
    label = GATE_STATUS_LABELS.get(result.status, result.status)
    metrics = result.metrics or {}
    rejected = metrics.get("rows_rejected", 0)
    read = metrics.get("rows_read", 0)
    return f"Validación finalizada: {label} ({rejected} de {read} filas rechazadas)."


def resolve_download(job: DmsExecutionJob, kind: str):
    """Devuelve (path relativo a MEDIA_ROOT, filename) para descarga."""
    if not job.report_path:
        return "", ""
    report_abs = storage_service.absolute_from_stored(job.report_path)
    if kind == "report":
        return job.report_path, "gate_report.json"
    if kind == "errors":
        csv_abs = report_abs.parent / "gate_issues.csv"
        return storage_service.relative_to_media(csv_abs), "gate_issues.csv"
    return "", ""
