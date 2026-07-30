"""Informe y evidencia FILE MATCH — Módulo 6 (match_report.md).

Presenta evidencia de un FileMatchJob finalizado (M5): resumen, diferencias
ofuscables, descargas con TTL/roles y certificado ligero.

Sin migración: reutiliza FileMatchJob + match_report.json / match_diff.csv.
"""

from __future__ import annotations

import json
import logging

from django.urls import reverse
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.services import detection_service, storage_service
from apps.dms.transform_execution.constants import DOWNLOAD_TTL
from apps.file_match.models import FileMatchJob
from apps.file_match.run.services import match_run_service as run_svc
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

CERTIFICATE_VERSION = "1.0"
REPORT_TTL = DOWNLOAD_TTL  # 7 días
DETAIL_UI_LIMIT = 200

FINAL_JOB_STATUSES = frozenset(
    {
        FileMatchJob.STATUS_COMPLETED,
        FileMatchJob.STATUS_FAILED,
        FileMatchJob.STATUS_PARTIAL,
    }
)

BUCKET_FILTERS = (
    "",
    "value_mismatch",
    "only_a",
    "only_b",
    "duplicate_key",
    "matched",
)


def resolve_role(user, project: Project) -> str | None:
    membership = project_service.get_membership(user, project)
    if membership is not None:
        return membership.role
    return None


def can_view_report(user, project: Project) -> bool:
    return resolve_role(user, project) is not None


def can_view_detail(user, project: Project) -> bool:
    """CO no ve tabla de diferencias con valores de fila."""
    role = resolve_role(user, project)
    return role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def can_reveal_values(user, project: Project) -> bool:
    role = resolve_role(user, project)
    return role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def can_download_files(user, project: Project) -> bool:
    role = resolve_role(user, project)
    return role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def can_view_certificate(user, project: Project) -> bool:
    return can_view_report(user, project)


def mask_value(raw) -> str:
    text = "" if raw is None else str(raw)
    if not text:
        return "—"
    if len(text) <= 2:
        return "**"
    return text[:2] + "***"


def job_finished_at(job: FileMatchJob):
    return job.finished_at or job.created_at


def is_download_expired(job: FileMatchJob) -> bool:
    ref = job_finished_at(job)
    if ref is None:
        return True
    if timezone.is_naive(ref):
        ref = timezone.make_aware(ref, timezone.utc)
    return timezone.now() > ref + REPORT_TTL


def ttl_remaining_label(job: FileMatchJob) -> str:
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


def is_job_final(job: FileMatchJob) -> bool:
    return job.status in FINAL_JOB_STATUSES


def _executed_by_label(job: FileMatchJob) -> str:
    if not job.executed_by_id:
        return ""
    user_obj = job.executed_by
    return (
        getattr(user_obj, "email", None)
        or getattr(user_obj, "username", "")
        or str(user_obj)
    )


def _load_detail_from_storage(job: FileMatchJob) -> list[dict]:
    preview = list(job.detail_preview or [])
    if not job.report_path:
        return preview
    try:
        path = storage_service.absolute_from_stored(job.report_path)
        if not path.is_file():
            return preview
        payload = json.loads(path.read_text(encoding="utf-8"))
        detail = payload.get("detail")
        if isinstance(detail, list):
            return detail
    except Exception:
        logger.exception("load detail from report job=%s", job.id)
    return preview


def _detail_for_ui(items: list[dict], *, reveal: bool, bucket: str) -> list[dict]:
    out = []
    for item in items or []:
        b = (item.get("bucket") or "").strip()
        if bucket and b != bucket:
            continue
        row = {
            "bucket": b,
            "key": item.get("key") or "",
            "count_a": item.get("count_a"),
            "count_b": item.get("count_b"),
            "diffs": [],
        }
        for diff in item.get("diffs") or []:
            va = diff.get("value_a")
            vb = diff.get("value_b")
            row["diffs"].append(
                {
                    "a": diff.get("a") or "",
                    "b": diff.get("b") or "",
                    "value_a_raw": "" if va is None else str(va),
                    "value_b_raw": "" if vb is None else str(vb),
                    "value_a_display": ("" if va is None else str(va)) if reveal else mask_value(va),
                    "value_b_display": ("" if vb is None else str(vb)) if reveal else mask_value(vb),
                }
            )
        out.append(row)
        if len(out) >= DETAIL_UI_LIMIT:
            break
    return out


def build_report_view(
    user,
    project: Project,
    job: FileMatchJob,
    *,
    bucket: str = "",
    reveal: bool = False,
) -> dict:
    base = run_svc.build_job_view(project, job)
    expired = is_download_expired(job)
    role = resolve_role(user, project)
    can_detail = can_view_detail(user, project)
    can_dl = can_download_files(user, project) and not expired and bool(job.report_path)
    can_reveal = can_reveal_values(user, project)
    reveal_effective = bool(reveal and can_reveal)

    bucket = (bucket or "").strip()
    if bucket not in BUCKET_FILTERS:
        bucket = ""

    detail_raw: list[dict] = []
    if can_detail:
        detail_raw = _load_detail_from_storage(job)
    detail_ui = _detail_for_ui(detail_raw, reveal=reveal_effective, bucket=bucket)

    downloads = {}
    if can_dl:
        downloads = run_svc.build_download_links(project.slug, job)

    return {
        **base,
        "role": role,
        "is_final": is_job_final(job),
        "is_expired": expired,
        "ttl_label": ttl_remaining_label(job),
        "can_view_detail": can_detail,
        "can_reveal_values": can_reveal,
        "can_download": can_dl,
        "can_certificate": can_view_certificate(user, project),
        "reveal": reveal_effective,
        "bucket_filter": bucket,
        "detail_rows": detail_ui,
        "detail_count": len(detail_ui),
        "detail_total_available": len(detail_raw) if can_detail else 0,
        "downloads": downloads,
        "certificate_url": reverse(
            "file_match:report_certificate",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        ),
        "executed_by": _executed_by_label(job),
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "rules_snapshot": job.rules_snapshot or {},
    }


def build_certificate(user, project: Project, job: FileMatchJob) -> dict:
    metrics = job.metrics or {}
    company_name = getattr(project.company, "name", "") or getattr(
        project.company, "name_short", ""
    ) or ""

    return {
        "certificate_version": CERTIFICATE_VERSION,
        "product": "FILE MATCH",
        "company": company_name,
        "project_slug": project.slug,
        "project_name": project.name,
        "job_id": str(job.id),
        "file_a_name": job.file_a_name,
        "file_a_size_bytes": job.file_a_size_bytes or 0,
        "file_a_size_label": detection_service.human_size(job.file_a_size_bytes or 0),
        "file_a_hash": job.file_a_hash or "",
        "file_b_name": job.file_b_name,
        "file_b_size_bytes": job.file_b_size_bytes or 0,
        "file_b_size_label": detection_service.human_size(job.file_b_size_bytes or 0),
        "file_b_hash": job.file_b_hash or "",
        "published_version": job.published_version_number,
        "verdict": job.verdict,
        "verdict_label": run_svc.VERDICT_LABELS.get(job.verdict, job.verdict or "—"),
        "verdict_tone": run_svc.VERDICT_TONE.get(job.verdict, "failed"),
        "is_success": job.verdict == FileMatchJob.VERDICT_PASSED,
        "is_partial": job.verdict == FileMatchJob.VERDICT_PARTIAL,
        "metrics": metrics,
        "executed_by": _executed_by_label(job),
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "is_expired": is_download_expired(job),
        "error_message": job.error_message or "",
    }


def certificate_json_payload(cert: dict) -> dict:
    def _iso(dt):
        if dt is None:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    metrics = cert.get("metrics") or {}
    return {
        "certificate_version": cert["certificate_version"],
        "product": cert["product"],
        "company": cert["company"],
        "project": {"slug": cert["project_slug"], "name": cert["project_name"]},
        "job_id": cert["job_id"],
        "files": {
            "a": {
                "original_filename": cert["file_a_name"],
                "size_bytes": cert["file_a_size_bytes"],
                "content_hash": (
                    f"sha256:{cert['file_a_hash']}" if cert["file_a_hash"] else ""
                ),
            },
            "b": {
                "original_filename": cert["file_b_name"],
                "size_bytes": cert["file_b_size_bytes"],
                "content_hash": (
                    f"sha256:{cert['file_b_hash']}" if cert["file_b_hash"] else ""
                ),
            },
        },
        "published_version": cert["published_version"],
        "result": {
            "verdict": cert["verdict"],
            "message": cert.get("error_message") or "",
        },
        "metrics": {
            "rows_a": metrics.get("rows_a", 0),
            "rows_b": metrics.get("rows_b", 0),
            "matched": metrics.get("matched", 0),
            "value_mismatch": metrics.get("value_mismatch", 0),
            "only_a": metrics.get("only_a", 0),
            "only_b": metrics.get("only_b", 0),
            "duplicate_key": metrics.get("duplicate_key", 0),
            "match_pct": metrics.get("match_pct"),
            "duration_ms": metrics.get("duration_ms"),
        },
        "executed_by": cert["executed_by"],
        "created_at": _iso(cert.get("created_at")),
        "finished_at": _iso(cert.get("finished_at")),
    }


def authorize_download(user, project: Project, job: FileMatchJob) -> OperationResult:
    if not can_download_files(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para descargar el informe de este proyecto.",
        )
    if not is_job_final(job):
        return OperationResult.failure(
            "validation_form",
            "La conciliación aún no finalizó.",
        )
    if is_download_expired(job):
        return OperationResult.failure(
            "validation_form",
            "La evidencia de descarga expiró. Los metadatos del job siguen disponibles.",
        )
    if not job.report_path:
        return OperationResult.failure(
            "not_found",
            "El archivo de descarga no está disponible.",
        )
    return OperationResult.success(user_message="OK")
