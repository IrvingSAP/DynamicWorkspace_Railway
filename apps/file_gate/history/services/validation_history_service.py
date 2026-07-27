"""Historial y auditoría FILE GATE — Módulo 5 (validation_history.md).

Lista, filtra y audita las corridas de validación de un proyecto. No recalcula
veredictos (H2): muestra lo persistido por el Módulo 3 en
DmsExecutionJob.input_suggestions["gate_result"] y aplica el TTL del Módulo 4.

Sin migración nueva: solo consulta sobre DmsExecutionJob.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import detection_service
from apps.file_gate.report.services import validation_report_service as report_svc
from apps.file_gate.run.services import validation_engine_service as engine
from apps.file_gate.run.services import validation_run_service as run_svc
from apps.projects.models import Project, ProjectMembership

PAGE_SIZE = 25

# Tope de corridas leídas por consulta (los filtros de estado/versión/TTL se
# resuelven en Python sobre el veredicto persistido en JSON).
MAX_SCAN = 500

TTL_ALL = "all"
TTL_ACTIVE = "active"
TTL_EXPIRED = "expired"
TTL_CHOICES = (TTL_ALL, TTL_ACTIVE, TTL_EXPIRED)

STATUS_ALL = "all"

# Estados de job que nunca entran al historial (corrida sin resultado).
NON_FINAL_JOB_STATUSES = (
    DmsExecutionJob.STATUS_UPLOADED,
    DmsExecutionJob.STATUS_QUEUED,
    DmsExecutionJob.STATUS_RUNNING,
)

_TONE_TO_SEVERITY = {
    "passed": "info",
    "partial": "warning",
    "failed": "error",
}


def status_options() -> list[dict]:
    return [
        {"value": code, "label": label}
        for code, label in run_svc.GATE_STATUS_LABELS.items()
    ]


# --------------------------------------------------------------------------- #
# Filtros (GET, sin Django Forms)
# --------------------------------------------------------------------------- #

def parse_filters(params) -> tuple[dict, dict]:
    """Normaliza el query string. Devuelve (filtros, errores inline)."""
    errors: dict[str, list[str]] = {}

    status = (params.get("status") or STATUS_ALL).strip()
    if status not in run_svc.GATE_STATUS_LABELS:
        status = STATUS_ALL

    ttl = (params.get("ttl") or TTL_ALL).strip()
    if ttl not in TTL_CHOICES:
        ttl = TTL_ALL

    filename = (params.get("filename") or "").strip()[:255]

    executed_by = (params.get("executed_by") or "").strip()
    if executed_by and not executed_by.isdigit():
        executed_by = ""

    version_raw = (params.get("version") or "").strip()
    version = None
    if version_raw:
        if version_raw.isdigit():
            version = int(version_raw)
        else:
            errors["version"] = ["La versión debe ser un número."]

    date_from = _parse_date_field(params.get("date_from"), "date_from", errors)
    date_to = _parse_date_field(params.get("date_to"), "date_to", errors)
    if date_from and date_to and date_from > date_to:
        errors["date_to"] = ["«Hasta» no puede ser anterior a «Desde»."]
        date_from = date_to = None

    page_raw = (params.get("page") or "1").strip()
    page = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1

    filters = {
        "status": status,
        "ttl": ttl,
        "filename": filename,
        "executed_by": executed_by,
        "version": version,
        "version_raw": version_raw,
        "date_from": date_from,
        "date_to": date_to,
        "page": page,
    }
    return filters, errors


def _parse_date_field(raw, key: str, errors: dict) -> object | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    value = parse_date(raw)
    if value is None:
        errors[key] = ["Fecha inválida (formato AAAA-MM-DD)."]
        return None
    return value


def has_active_filters(filters: dict) -> bool:
    return bool(
        filters["status"] != STATUS_ALL
        or filters["ttl"] != TTL_ALL
        or filters["filename"]
        or filters["executed_by"]
        or filters["version"] is not None
        or filters["date_from"]
        or filters["date_to"]
    )


def _querystring(filters: dict, **overrides) -> str:
    data = {
        "status": filters["status"] if filters["status"] != STATUS_ALL else "",
        "ttl": filters["ttl"] if filters["ttl"] != TTL_ALL else "",
        "filename": filters["filename"],
        "executed_by": filters["executed_by"],
        "version": filters["version_raw"],
        "date_from": filters["date_from"].isoformat() if filters["date_from"] else "",
        "date_to": filters["date_to"].isoformat() if filters["date_to"] else "",
    }
    data.update(overrides)
    return urlencode({k: v for k, v in data.items() if v})


# --------------------------------------------------------------------------- #
# Consulta
# --------------------------------------------------------------------------- #

def _start_of_day(value):
    return _aware(datetime.combine(value, time.min))


def _aware(value: datetime):
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _filtered_queryset(project: Project, filters: dict):
    """H1/H8: solo jobs del proyecto. Filtros que resuelve la base de datos."""
    qs = (
        DmsExecutionJob.objects.filter(project=project)
        .exclude(status__in=NON_FINAL_JOB_STATUSES)
        .select_related("executed_by", "version")
        .annotate(effective_at=Coalesce("finished_at", "created_at"))
        .order_by("-effective_at", "-created_at")
    )
    if filters["filename"]:
        qs = qs.filter(input_original_filename__icontains=filters["filename"])
    if filters["executed_by"]:
        qs = qs.filter(executed_by_id=filters["executed_by"])
    if filters["date_from"]:
        qs = qs.filter(effective_at__gte=_start_of_day(filters["date_from"]))
    if filters["date_to"]:
        qs = qs.filter(
            effective_at__lt=_start_of_day(filters["date_to"] + timedelta(days=1))
        )
    return qs


def _matches_python_filters(row: dict, filters: dict) -> bool:
    """H6: filtros aditivos (AND) sobre datos que viven en el JSON del job."""
    if filters["status"] != STATUS_ALL and row["gate_status"] != filters["status"]:
        return False
    if filters["version"] is not None and row["version"] != filters["version"]:
        return False
    if filters["ttl"] == TTL_ACTIVE and row["is_expired"]:
        return False
    if filters["ttl"] == TTL_EXPIRED and not row["is_expired"]:
        return False
    return True


def build_row(project: Project, job: DmsExecutionJob) -> dict:
    """Fila de auditoría: metadatos + veredicto persistido + TTL + enlaces."""
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    metrics = gate.get("metrics") or {}
    snapshot = gate.get("schema_snapshot") or {}
    gate_status = gate.get("status") or job.status
    tone = run_svc.GATE_STATUS_TONE.get(gate_status, "failed")
    content_hash = job.input_content_hash or ""
    expired = report_svc.is_download_expired(job)

    version = gate.get("published_version_number") or snapshot.get("version")
    if version is None and job.version_id:
        version = job.version.version_number

    executed_by = ""
    if job.executed_by_id:
        user_obj = job.executed_by
        executed_by = (
            getattr(user_obj, "email", None)
            or getattr(user_obj, "username", "")
            or str(user_obj)
        )

    return {
        "job": job,
        "id": str(job.id),
        "short_id": str(job.id)[:8],
        "filename": job.input_original_filename or "—",
        "size_bytes": job.input_size_bytes or 0,
        "size_label": detection_service.human_size(job.input_size_bytes or 0),
        "content_hash": content_hash,
        "content_hash_short": f"{content_hash[:4]}…{content_hash[-2:]}" if content_hash else "—",
        "version": version,
        "gate_status": gate_status,
        "gate_status_label": run_svc.GATE_STATUS_LABELS.get(gate_status, gate_status),
        "gate_tone": tone,
        "severity": _TONE_TO_SEVERITY.get(tone, "error"),
        "is_success": gate_status
        in (engine.STATUS_PASSED, engine.STATUS_PASSED_WITH_WARNINGS),
        "rows_read": metrics.get("rows_read", job.rows_read or 0),
        "rows_rejected": metrics.get("rows_rejected"),
        "reject_rate": metrics.get("reject_rate_percent"),
        "executed_by": executed_by,
        "started_at": job.started_at,
        "finished_at": report_svc.job_finished_at(job),
        "is_expired": expired,
        "ttl_label": report_svc.ttl_remaining_label(job),
        "result_url": reverse(
            "file_gate:run_result",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
        "report_url": reverse(
            "file_gate:report_detail",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
        "certificate_url": reverse(
            "file_gate:report_certificate",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
    }


def executed_by_options(project: Project) -> list[dict]:
    users = (
        get_user_model()
        .objects.filter(dms_execution_jobs__project=project)
        .exclude(dms_execution_jobs__status__in=NON_FINAL_JOB_STATUSES)
        .distinct()
        .order_by("email")
    )
    return [
        {
            "value": str(user.pk),
            "label": getattr(user, "email", "") or getattr(user, "username", "") or str(user),
        }
        for user in users
    ]


def version_options(project: Project) -> list[int]:
    numbers = (
        DmsExecutionJob.objects.filter(project=project)
        .exclude(status__in=NON_FINAL_JOB_STATUSES)
        .exclude(version__isnull=True)
        .values_list("version__version_number", flat=True)
        .distinct()
    )
    return sorted({int(n) for n in numbers if n is not None}, reverse=True)


# --------------------------------------------------------------------------- #
# Contexto de pantalla
# --------------------------------------------------------------------------- #

def build_history_context(user, project: Project, params) -> dict:
    filters, errors = parse_filters(params)

    role = report_svc.resolve_role(user, project)
    jobs = list(_filtered_queryset(project, filters)[:MAX_SCAN])

    # H2/H9: solo corridas finalizadas; el veredicto se lee, no se recalcula.
    universe = [
        build_row(project, job) for job in jobs if report_svc.is_job_final(job)
    ]
    rows = [row for row in universe if _matches_python_filters(row, filters)]

    # H10: los contadores describen el universo filtrado completo, no la página.
    stats = {
        "total": len(rows),
        "passed": sum(1 for row in rows if row["is_success"]),
        "failed": sum(1 for row in rows if row["gate_tone"] == "failed"),
        "expired": sum(1 for row in rows if row["is_expired"]),
    }

    total = len(rows)
    total_pages = max(1, -(-total // PAGE_SIZE))
    page = min(filters["page"], total_pages)
    start = (page - 1) * PAGE_SIZE
    page_rows = rows[start : start + PAGE_SIZE]

    return {
        "rows": page_rows,
        "stats": stats,
        "filters": filters,
        "errors": errors,
        "role": role,
        "is_company_viewer": role == ProjectMembership.ROLE_CO,
        "can_download": report_svc.can_download_files(user, project),
        "can_execute": run_svc.user_can_execute(user, project),
        "has_any_job": bool(universe),
        "has_active_filters": has_active_filters(filters),
        "status_options": status_options(),
        "version_options": version_options(project),
        "executed_by_options": executed_by_options(project),
        "ttl_days": report_svc.REPORT_TTL.days,
        "page": page,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        "showing_from": start + 1 if page_rows else 0,
        "showing_to": start + len(page_rows),
        "scan_truncated": len(jobs) >= MAX_SCAN,
        "max_scan": MAX_SCAN,
        "prev_query": _querystring(filters, page=page - 1) if page > 1 else "",
        "next_query": _querystring(filters, page=page + 1) if page < total_pages else "",
    }
