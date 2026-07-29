"""Historial de generaciones Reverse Studio — Módulo 6 (history.md).

Lista y filtra DmsExecutionJob del proyecto KIND_REVERSE. No recalcula
resultados (HIS2). Descargas vía enlaces M5 + TTL DMS.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import detection_service
from apps.dms.transform_execution.constants import DOWNLOAD_TTL
from apps.dms.transform_execution.services import execution_service
from apps.projects.models import Project, ProjectMembership
from apps.reverse_studio.run.services import generate_run_service

PAGE_SIZE = 25
MAX_SCAN = 500

TTL_ALL = "all"
TTL_ACTIVE = "active"
TTL_EXPIRED = "expired"
TTL_CHOICES = (TTL_ALL, TTL_ACTIVE, TTL_EXPIRED)

STATUS_ALL = "all"
STATUS_LABELS = {
    DmsExecutionJob.STATUS_COMPLETED: "Completado",
    DmsExecutionJob.STATUS_PARTIAL: "Parcial",
    DmsExecutionJob.STATUS_FAILED: "Fallido",
}

NON_FINAL_JOB_STATUSES = (
    DmsExecutionJob.STATUS_UPLOADED,
    DmsExecutionJob.STATUS_QUEUED,
    DmsExecutionJob.STATUS_RUNNING,
)

FINAL_STATUSES = tuple(STATUS_LABELS.keys())


def status_options() -> list[dict]:
    return [{"value": code, "label": label} for code, label in STATUS_LABELS.items()]


def parse_filters(params) -> tuple[dict, dict]:
    errors: dict[str, list[str]] = {}

    status = (params.get("status") or STATUS_ALL).strip()
    if status not in STATUS_LABELS:
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


def _parse_date_field(raw, key: str, errors: dict):
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


def _start_of_day(value):
    return _aware(datetime.combine(value, time.min))


def _aware(value: datetime):
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _filtered_queryset(project: Project, filters: dict):
    """HIS1/HIS8: solo jobs del proyecto. Excluye preview y estados no finales."""
    qs = (
        DmsExecutionJob.objects.filter(project=project)
        .exclude(job_type=DmsExecutionJob.JOB_PREVIEW)
        .exclude(status__in=NON_FINAL_JOB_STATUSES)
        .filter(
            Q(job_type=DmsExecutionJob.JOB_FULL)
            | Q(status__in=FINAL_STATUSES)
        )
        .select_related("executed_by", "version")
        .annotate(effective_at=Coalesce("finished_at", "created_at"))
        .order_by("-effective_at", "-created_at")
    )
    if filters["status"] != STATUS_ALL:
        qs = qs.filter(status=filters["status"])
    if filters["filename"]:
        qs = qs.filter(input_original_filename__icontains=filters["filename"])
    if filters["executed_by"]:
        qs = qs.filter(executed_by_id=filters["executed_by"])
    if filters["version"] is not None:
        qs = qs.filter(version__version_number=filters["version"])
    if filters["date_from"]:
        qs = qs.filter(effective_at__gte=_start_of_day(filters["date_from"]))
    if filters["date_to"]:
        qs = qs.filter(
            effective_at__lt=_start_of_day(filters["date_to"] + timedelta(days=1))
        )
    return qs


def _matches_ttl(row: dict, filters: dict) -> bool:
    if filters["ttl"] == TTL_ACTIVE and row["is_expired"]:
        return False
    if filters["ttl"] == TTL_EXPIRED and not row["is_expired"]:
        return False
    return True


def _hash_short(value: str) -> str:
    value = value or ""
    if len(value) < 8:
        return value or "—"
    return f"{value[:4]}…{value[-2:]}"


def _executed_by_label(job: DmsExecutionJob) -> str:
    if not job.executed_by_id:
        return "—"
    user_obj = job.executed_by
    return (
        getattr(user_obj, "email", None)
        or getattr(user_obj, "username", "")
        or str(user_obj)
    )


def build_row(project: Project, job: DmsExecutionJob, *, can_download: bool) -> dict:
    content_hash = job.input_content_hash or ""
    expired = execution_service.is_download_expired(job)
    status = job.status
    downloads = {}
    if (
        can_download
        and not expired
        and status
        in {DmsExecutionJob.STATUS_COMPLETED, DmsExecutionJob.STATUS_PARTIAL}
    ):
        downloads = execution_service.build_download_links(
            project.slug,
            job,
            url_namespace="reverse_studio",
            url_names=generate_run_service.DOWNLOAD_URL_NAMES,
        )

    version_number = job.version.version_number if job.version_id else None
    tone = "ok"
    if status == DmsExecutionJob.STATUS_PARTIAL:
        tone = "partial"
    elif status == DmsExecutionJob.STATUS_FAILED:
        tone = "fail"

    return {
        "job": job,
        "id": str(job.id),
        "short_id": str(job.id)[:8],
        "filename": job.input_original_filename or "—",
        "size_bytes": job.input_size_bytes or 0,
        "size_label": detection_service.human_size(job.input_size_bytes or 0),
        "content_hash": content_hash,
        "content_hash_short": _hash_short(content_hash),
        "version": version_number,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "tone": tone,
        "is_success": status == DmsExecutionJob.STATUS_COMPLETED,
        "is_problem": status
        in {DmsExecutionJob.STATUS_PARTIAL, DmsExecutionJob.STATUS_FAILED},
        "rows_read": job.rows_read or 0,
        "rows_ok": job.rows_ok or 0,
        "rows_rejected": job.rows_rejected or 0,
        "output_filename": job.output_filename or "",
        "executed_by": _executed_by_label(job),
        "started_at": job.started_at,
        "finished_at": job.finished_at or job.created_at,
        "is_expired": expired,
        "downloads": downloads,
        "detail_url": reverse(
            "reverse_studio:history_detail",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
        "error_message": job.error_message or "",
    }


def build_detail(project: Project, job: DmsExecutionJob, *, can_download: bool) -> dict:
    row = build_row(project, job, can_download=can_download)
    row["input_mime_type"] = job.input_mime_type or ""
    row["output_size_label"] = detection_service.human_size(job.output_size_bytes or 0)
    row["job_type"] = job.job_type
    return row


def executed_by_options(project: Project) -> list[dict]:
    users = (
        get_user_model()
        .objects.filter(dms_execution_jobs__project=project)
        .exclude(dms_execution_jobs__status__in=NON_FINAL_JOB_STATUSES)
        .exclude(dms_execution_jobs__job_type=DmsExecutionJob.JOB_PREVIEW)
        .distinct()
        .order_by("email", "username")
    )
    return [
        {
            "value": str(user.pk),
            "label": getattr(user, "email", "")
            or getattr(user, "username", "")
            or str(user),
        }
        for user in users
    ]


def version_options(project: Project) -> list[int]:
    numbers = (
        DmsExecutionJob.objects.filter(project=project)
        .exclude(status__in=NON_FINAL_JOB_STATUSES)
        .exclude(job_type=DmsExecutionJob.JOB_PREVIEW)
        .exclude(version__isnull=True)
        .values_list("version__version_number", flat=True)
        .distinct()
    )
    return sorted({int(n) for n in numbers if n is not None}, reverse=True)


def user_can_view_history(user, project: Project) -> bool:
    """Cualquier usuario con acceso al proyecto (membresía o visibilidad compañía)."""
    from apps.reverse_studio.projects.services import reverse_project_service

    return reverse_project_service.user_can_view(user, project)


def build_history_context(user, project: Project, params) -> dict:
    filters, errors = parse_filters(params)
    can_download = generate_run_service.user_can_download(user, project)
    from apps.projects.services import project_service

    membership = project_service.get_membership(user, project)
    role = membership.role if membership else ProjectMembership.ROLE_CO

    jobs = list(_filtered_queryset(project, filters)[:MAX_SCAN])
    universe = [build_row(project, job, can_download=can_download) for job in jobs]
    any_jobs = (
        DmsExecutionJob.objects.filter(project=project)
        .exclude(status__in=NON_FINAL_JOB_STATUSES)
        .exclude(job_type=DmsExecutionJob.JOB_PREVIEW)
        .exists()
    )

    rows = [row for row in universe if _matches_ttl(row, filters)]

    stats = {
        "total": len(rows),
        "completed": sum(1 for row in rows if row["is_success"]),
        "problems": sum(1 for row in rows if row["is_problem"]),
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
        "is_consulta": role == ProjectMembership.ROLE_CO or membership is None,
        "can_download": can_download,
        "can_execute": execution_service.user_can_execute(user, project),
        "has_any_job": any_jobs,
        "has_active_filters": has_active_filters(filters),
        "status_options": status_options(),
        "version_options": version_options(project),
        "executed_by_options": executed_by_options(project),
        "ttl_days": DOWNLOAD_TTL.days,
        "page": page,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        "showing_from": start + 1 if page_rows else 0,
        "showing_to": start + len(page_rows),
        "scan_truncated": len(jobs) >= MAX_SCAN,
        "max_scan": MAX_SCAN,
        "prev_query": _querystring(filters, page=page - 1) if page > 1 else "",
        "next_query": _querystring(filters, page=page + 1) if page < total_pages else "",
        "run_hub_url": reverse(
            "reverse_studio:run_hub", kwargs={"project_slug": project.slug}
        ),
    }


def get_job_detail(user, project: Project, job_id) -> dict | None:
    job = execution_service.get_job(project, job_id)
    if job is None:
        return None
    if job.job_type == DmsExecutionJob.JOB_PREVIEW:
        return None
    if job.status in NON_FINAL_JOB_STATUSES:
        return None
    can_download = generate_run_service.user_can_download(user, project)
    return build_detail(project, job, can_download=can_download)
