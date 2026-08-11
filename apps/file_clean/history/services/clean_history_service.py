"""Historial File Clean — Módulo 6 (clean_history.md).

Lista y detalla CleanJob. TTL de artifacts vía clean_run_service (7 días).
CO: metadatos; PA/ED/GE: descargas si vigentes. Borrado solo de corridas propias.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.dms.file_intake.services import detection_service, storage_service
from apps.file_clean.models import CleanJob
from apps.file_clean.run.services import clean_run_service as run_svc
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

MSG_DELETED = "Corrida eliminada del historial."
MSG_DELETED_MANY = "Se eliminaron {n} corridas propias del historial."
MSG_NONE_OWN = "No tiene corridas propias para eliminar en este proyecto."
MSG_NOT_FOUND = "No se encontró la corrida en este proyecto."
MSG_NOT_OWNER = "Solo puede eliminar corridas que usted ejecutó."
MSG_NO_PERMISSION = "No tiene permiso para ver el historial de este proyecto."
MSG_UNEXPECTED = (
    "No se pudo eliminar la corrida. Si el problema continúa, contacte al administrador."
)

PAGE_SIZE = 25
MAX_SCAN = 500

TTL_ALL = "all"
TTL_ACTIVE = "active"
TTL_EXPIRED = "expired"
TTL_CHOICES = (TTL_ALL, TTL_ACTIVE, TTL_EXPIRED)

STATUS_ALL = "all"
STATUS_FILTERABLE = {
    CleanJob.STATUS_COMPLETED,
    CleanJob.STATUS_FAILED,
}

NON_FINAL_STATUSES = (CleanJob.STATUS_QUEUED, CleanJob.STATUS_RUNNING)


def user_can_view_history(user, project: Project) -> bool:
    from apps.file_clean.projects.services import clean_project_service

    return clean_project_service.user_can_view(user, project)


def resolve_role(user, project: Project) -> str:
    membership = project_service.get_membership(user, project)
    if membership is not None:
        return membership.role
    return ProjectMembership.ROLE_CO


def status_options() -> list[dict]:
    return [
        {"value": CleanJob.STATUS_COMPLETED, "label": run_svc.STATUS_LABELS[CleanJob.STATUS_COMPLETED]},
        {"value": CleanJob.STATUS_FAILED, "label": run_svc.STATUS_LABELS[CleanJob.STATUS_FAILED]},
    ]


def parse_filters(params) -> tuple[dict, dict]:
    errors: dict[str, list[str]] = {}

    status = (params.get("status") or STATUS_ALL).strip()
    if status not in STATUS_FILTERABLE:
        status = STATUS_ALL

    ttl = (params.get("ttl") or TTL_ALL).strip()
    if ttl not in TTL_CHOICES:
        ttl = TTL_ALL

    filename = (params.get("filename") or "").strip()[:255]
    hash_q = (params.get("hash") or "").strip()[:64]

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

    dry_run = (params.get("dry_run") or "all").strip()
    if dry_run not in {"all", "yes", "no"}:
        dry_run = "all"

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
        "hash": hash_q,
        "executed_by": executed_by,
        "version": version,
        "version_raw": version_raw,
        "dry_run": dry_run,
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
        or filters["hash"]
        or filters["executed_by"]
        or filters["version"] is not None
        or filters["dry_run"] != "all"
        or filters["date_from"]
        or filters["date_to"]
    )


def _querystring(filters: dict, **overrides) -> str:
    data = {
        "status": filters["status"] if filters["status"] != STATUS_ALL else "",
        "ttl": filters["ttl"] if filters["ttl"] != TTL_ALL else "",
        "filename": filters["filename"],
        "hash": filters["hash"],
        "executed_by": filters["executed_by"],
        "version": filters["version_raw"],
        "dry_run": filters["dry_run"] if filters["dry_run"] != "all" else "",
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


def _base_queryset(project: Project):
    return (
        CleanJob.objects.filter(project=project)
        .exclude(status__in=NON_FINAL_STATUSES)
        .select_related("executed_by", "published_version")
        .annotate(effective_at=Coalesce("finished_at", "created_at"))
        .order_by("-effective_at", "-created_at")
    )


def _filtered_queryset(project: Project, filters: dict):
    qs = _base_queryset(project)
    if filters["status"] != STATUS_ALL:
        qs = qs.filter(status=filters["status"])
    if filters["filename"]:
        qs = qs.filter(input_original_filename__icontains=filters["filename"])
    if filters["hash"]:
        qs = qs.filter(
            Q(input_content_hash__istartswith=filters["hash"])
            | Q(output_content_hash__istartswith=filters["hash"])
        )
    if filters["executed_by"]:
        qs = qs.filter(executed_by_id=filters["executed_by"])
    if filters["version"] is not None:
        qs = qs.filter(published_version_number=filters["version"])
    if filters["dry_run"] == "yes":
        qs = qs.filter(dry_run=True)
    elif filters["dry_run"] == "no":
        qs = qs.filter(dry_run=False)
    if filters["date_from"]:
        qs = qs.filter(effective_at__gte=_start_of_day(filters["date_from"]))
    if filters["date_to"]:
        qs = qs.filter(
            effective_at__lt=_start_of_day(filters["date_to"] + timedelta(days=1))
        )
    return qs


def can_delete_job(user, job: CleanJob) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if not job.executed_by_id:
        return False
    return job.executed_by_id == user.id


def _job_storage_root(project: Project, job: CleanJob):
    return storage_service.job_input_dir(
        project.company_id, project.id, job.id
    ).parent


def _purge_job_storage(project: Project, job: CleanJob) -> None:
    root = _job_storage_root(project, job)
    if not root.exists():
        return
    try:
        shutil.rmtree(root, ignore_errors=False)
    except OSError:
        logger.exception(
            "purge_job_storage failed project=%s job=%s path=%s",
            project.id,
            job.id,
            root,
        )


def _own_jobs_queryset(user, project: Project):
    return (
        CleanJob.objects.filter(project=project, executed_by=user)
        .exclude(status__in=NON_FINAL_STATUSES)
        .order_by("-created_at")
    )


def delete_own_job(user, project: Project, job_id) -> dict:
    if not user_can_view_history(user, project):
        return {
            "ok": False,
            "error_code": "permission_denied",
            "user_message": MSG_NO_PERMISSION,
            "errors": {},
        }

    job = (
        CleanJob.objects.filter(project=project, pk=job_id)
        .exclude(status__in=NON_FINAL_STATUSES)
        .first()
    )
    if job is None:
        return {
            "ok": False,
            "error_code": "not_found",
            "user_message": MSG_NOT_FOUND,
            "errors": {},
        }
    if not can_delete_job(user, job):
        return {
            "ok": False,
            "error_code": "permission_denied",
            "user_message": MSG_NOT_OWNER,
            "errors": {},
        }

    try:
        _purge_job_storage(project, job)
        job.delete()
    except Exception:
        logger.exception("delete_own_job failed project=%s job=%s", project.id, job_id)
        return {
            "ok": False,
            "error_code": "unexpected",
            "user_message": MSG_UNEXPECTED,
            "errors": {},
        }

    return {
        "ok": True,
        "error_code": None,
        "user_message": MSG_DELETED,
        "errors": {},
        "deleted_count": 1,
    }


def delete_own_jobs(user, project: Project) -> dict:
    if not user_can_view_history(user, project):
        return {
            "ok": False,
            "error_code": "permission_denied",
            "user_message": MSG_NO_PERMISSION,
            "errors": {},
            "deleted_count": 0,
        }

    jobs = list(_own_jobs_queryset(user, project))
    if not jobs:
        return {
            "ok": False,
            "error_code": "not_found",
            "user_message": MSG_NONE_OWN,
            "errors": {},
            "deleted_count": 0,
        }

    deleted = 0
    try:
        for job in jobs:
            _purge_job_storage(project, job)
            job.delete()
            deleted += 1
    except Exception:
        logger.exception(
            "delete_own_jobs failed project=%s user=%s deleted=%s",
            project.id,
            getattr(user, "id", None),
            deleted,
        )
        if deleted:
            return {
                "ok": True,
                "error_code": None,
                "user_message": MSG_DELETED_MANY.format(n=deleted),
                "errors": {},
                "deleted_count": deleted,
            }
        return {
            "ok": False,
            "error_code": "unexpected",
            "user_message": MSG_UNEXPECTED,
            "errors": {},
            "deleted_count": 0,
        }

    return {
        "ok": True,
        "error_code": None,
        "user_message": MSG_DELETED_MANY.format(n=deleted),
        "errors": {},
        "deleted_count": deleted,
    }


def build_row(project: Project, job: CleanJob, *, user=None) -> dict:
    metrics = job.metrics or {}
    expired = run_svc.is_download_expired(job)
    content_hash = job.input_content_hash or ""
    executed_by = ""
    if job.executed_by_id:
        user_obj = job.executed_by
        executed_by = (
            getattr(user_obj, "email", None)
            or getattr(user_obj, "username", "")
            or str(user_obj)
        )

    can_dl = (
        user is not None
        and run_svc.user_can_download(user, project)
        and not expired
        and not job.dry_run
        and bool(job.output_stored_path or job.change_log_path)
    )

    return {
        "job": job,
        "id": str(job.id),
        "short_id": str(job.id)[:8],
        "filename": job.input_original_filename or "—",
        "size_label": detection_service.human_size(job.input_size_bytes or 0),
        "content_hash": content_hash,
        "content_hash_short": f"{content_hash[:8]}…" if content_hash else "—",
        "version": job.published_version_number,
        "status": job.status,
        "status_label": run_svc.STATUS_LABELS.get(job.status, job.status),
        "is_success": job.status == CleanJob.STATUS_COMPLETED,
        "is_failed": job.status == CleanJob.STATUS_FAILED,
        "dry_run": job.dry_run,
        "rows_read": metrics.get("rows_read"),
        "rows_written": metrics.get("rows_written"),
        "cells_changed": metrics.get("cells_changed"),
        "dedupe_count": metrics.get("dedupe_count"),
        "executed_by": executed_by,
        "finished_at": run_svc.job_finished_at(job),
        "is_expired": expired,
        "ttl_label": run_svc.ttl_remaining_label(job),
        "can_delete": can_delete_job(user, job) if user is not None else False,
        "can_download": can_dl,
        "result_url": reverse(
            "file_clean:run_result",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
        "detail_url": reverse(
            "file_clean:history_detail",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
    }


def executed_by_options(project: Project) -> list[dict]:
    users = (
        get_user_model()
        .objects.filter(file_clean_jobs__project=project)
        .exclude(file_clean_jobs__status__in=NON_FINAL_STATUSES)
        .distinct()
        .order_by("email")
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
        CleanJob.objects.filter(project=project)
        .exclude(status__in=NON_FINAL_STATUSES)
        .values_list("published_version_number", flat=True)
        .distinct()
    )
    return sorted({int(n) for n in numbers if n is not None}, reverse=True)


def build_history_context(user, project: Project, params) -> dict:
    filters, errors = parse_filters(params)
    role = resolve_role(user, project)

    qs = _filtered_queryset(project, filters)
    jobs = list(qs[:MAX_SCAN])

    universe = [build_row(project, job, user=user) for job in jobs]

    rows = universe
    if filters["ttl"] == TTL_ACTIVE:
        rows = [row for row in rows if not row["is_expired"]]
    elif filters["ttl"] == TTL_EXPIRED:
        rows = [row for row in rows if row["is_expired"]]

    stats = {
        "total": len(rows),
        "completed": sum(1 for row in rows if row["is_success"]),
        "failed": sum(1 for row in rows if row["is_failed"]),
        "expired": sum(1 for row in rows if row["is_expired"]),
    }

    total = len(rows)
    total_pages = max(1, -(-total // PAGE_SIZE))
    page = min(filters["page"], total_pages)
    start = (page - 1) * PAGE_SIZE
    page_rows = rows[start : start + PAGE_SIZE]

    has_any_job = _base_queryset(project).exists()
    can_delete_own_any = (
        user_can_view_history(user, project)
        and _own_jobs_queryset(user, project).exists()
    )

    return {
        "rows": page_rows,
        "stats": stats,
        "filters": filters,
        "errors": errors,
        "role": role,
        "is_company_viewer": role == ProjectMembership.ROLE_CO,
        "can_download": run_svc.user_can_download(user, project),
        "can_execute": run_svc.user_can_execute(user, project),
        "can_delete_own_any": can_delete_own_any,
        "has_any_job": has_any_job,
        "has_active_filters": has_active_filters(filters),
        "status_options": status_options(),
        "version_options": version_options(project),
        "executed_by_options": executed_by_options(project),
        "ttl_days": run_svc.ARTIFACT_TTL.days,
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


def build_detail_context(user, project: Project, job: CleanJob) -> dict:
    """Proyección estable de detalle (API-ready)."""
    row = build_row(project, job, user=user)
    view = run_svc.build_job_view(project, job)
    role = resolve_role(user, project)
    can_dl = run_svc.user_can_download(user, project) and not row["is_expired"] and not job.dry_run

    rules_snapshot = job.rules_snapshot or []
    enabled_rules = [r for r in rules_snapshot if isinstance(r, dict) and r.get("enabled", True)]
    enabled_rules = sorted(enabled_rules, key=lambda r: int(r.get("sort_order") or 0))

    return {
        "row": row,
        "view": view,
        "role": role,
        "is_company_viewer": role == ProjectMembership.ROLE_CO,
        "can_download": can_dl,
        "can_delete": can_delete_job(user, job),
        "ttl_days": run_svc.ARTIFACT_TTL.days,
        "rules_enabled": [
            {
                "code": r.get("code") or "",
                "field_name": r.get("field_name") or "—",
                "sort_order": r.get("sort_order"),
            }
            for r in enabled_rules
        ],
        "job_id": str(job.id),
        "status": job.status,
        "published_version_number": job.published_version_number,
        "dry_run": job.dry_run,
        "metrics": job.metrics or {},
        "input_hash": job.input_content_hash or "",
        "output_hash": job.output_content_hash or "",
        "executed_by": row["executed_by"],
        "finished_at": row["finished_at"],
        "created_at": job.created_at,
    }
