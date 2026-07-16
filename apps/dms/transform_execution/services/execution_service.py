"""Orquestación dry-run / ejecución completa de DmsExecutionJob."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone as dj_timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.field_mapping.services import field_mapping_persistence_service
from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import file_intake_persistence_service, storage_service
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.services import target_persistence_service
from apps.dms.transform_execution.constants import PREVIEW_ROW_LIMIT, SYNC_MAX_BYTES
from apps.dms.transform_execution.services import (
    download_token_service,
    execution_report_service,
    filename_service,
    row_mapping_service,
    source_parser_service,
    target_serializer_service,
)
from apps.projects.models import Project
from apps.projects.services import project_service

logger = logging.getLogger(__name__)


def user_can_execute(user, project: Project) -> bool:
    return file_intake_persistence_service.user_can_upload_production(user, project)


def user_can_view_history(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    return membership is not None


def _load_bundle(version):
    source = source_persistence_service.profile_to_dict(version.source_profile)
    target = target_persistence_service.profile_to_dict(version.target_profile)
    mappings = field_mapping_persistence_service.set_to_dict(version.field_mapping_set)
    return source, target, mappings.get("mappings") or []


def get_job(project: Project, job_id) -> DmsExecutionJob | None:
    return (
        DmsExecutionJob.objects.select_related(
            "version",
            "version__source_profile",
            "version__target_profile",
            "version__field_mapping_set",
            "executed_by",
        )
        .filter(project=project, id=job_id)
        .first()
    )


def _process_rows(parsed_rows, mappings, target, *, project_id: str | None = None):
    generators = row_mapping_service.GeneratorState(project_id=project_id)
    target_fields = target.get("fields") or []
    ok_rows = []
    errors = []
    policy = (target.get("write_validation") or {}).get("policy") or "reject_row"

    for item in parsed_rows:
        if hasattr(item, "data"):
            source_row = item.data
            line_no = item.line
        else:
            source_row = item
            line_no = 1
        target_row, row_errors = row_mapping_service.map_row(
            source_row,
            mappings,
            target_fields,
            row_number=line_no,
            generators=generators,
        )
        if row_errors:
            errors.extend(row_errors)
            if policy == "abort":
                break
            if policy in {"reject_row", "error"}:
                continue
        ok_rows.append({"source": source_row, "target": target_row, "line": line_no})
    return ok_rows, errors


def _merge_parse_and_map(parse_result, mappings, target, *, project_id: str | None = None):
    ok_items, map_errors = _process_rows(
        parse_result.rows, mappings, target, project_id=project_id
    )
    errors = list(parse_result.errors) + list(map_errors)
    rows_read = parse_result.rows_read or (
        len(parse_result.rows) + len({err.get("line") for err in parse_result.errors})
    )
    messages = list(getattr(parse_result, "messages", None) or [])
    return ok_items, errors, rows_read, messages


def dry_run_job(user, project: Project, job_id, *, limit: int = PREVIEW_ROW_LIMIT) -> OperationResult:
    if not user_can_execute(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para ejecutar transformaciones de este proyecto.",
        )
    job = get_job(project, job_id)
    if job is None:
        return OperationResult.failure("not_found", "Job no encontrado.")
    if not job.input_stored_path:
        return OperationResult.failure(
            "validation_form",
            "El job no tiene archivo de entrada subido.",
        )

    try:
        source, target, mappings = _load_bundle(job.version)
        path = storage_service.absolute_from_stored(job.input_stored_path)
        parse_result = source_parser_service.parse_source_file(path, source, limit=limit)
        ok_rows, errors, rows_read, capture_messages = _merge_parse_and_map(
            parse_result, mappings, target, project_id=str(project.id)
        )
    except source_parser_service.ParseError as exc:
        return OperationResult.failure("validation_form", str(exc))
    except Exception:
        logger.exception("dry_run_job unexpected job=%s", job_id)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al previsualizar. Si persiste, contacte al administrador.",
        )

    preview = [
        {
            "line": item["line"],
            "source": item["source"],
            "target": item["target"],
        }
        for item in ok_rows[:limit]
    ]
    localized_errors, localized_messages = execution_report_service.localize_payload_errors(
        errors, capture_messages
    )

    return OperationResult.success(
        user_message="Preview generado correctamente.",
        payload={
            "job_id": str(job.id),
            "rows_read": rows_read,
            "rows_ok": len(ok_rows),
            "rows_rejected": len({err["line"] for err in localized_errors}),
            "preview_rows": preview,
            "row_errors": localized_errors[:200],
            "messages": localized_messages,
            "target_fields": [f.get("name") for f in (target.get("fields") or [])],
            "source_fields": [f.get("name") for f in (source.get("fields") or [])],
        },
    )


@transaction.atomic
def run_full_job(user, project: Project, job_id) -> OperationResult:
    if not user_can_execute(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para ejecutar transformaciones de este proyecto.",
        )
    job = get_job(project, job_id)
    if job is None:
        return OperationResult.failure("not_found", "Job no encontrado.")
    if not job.input_stored_path:
        return OperationResult.failure(
            "validation_form",
            "El job no tiene archivo de entrada subido.",
        )
    if job.input_size_bytes and job.input_size_bytes > SYNC_MAX_BYTES:
        return OperationResult.failure(
            "validation_form",
            "Archivos mayores a 50 MB requieren ejecución asíncrona (Fase 2).",
        )
    if job.status in {
        DmsExecutionJob.STATUS_RUNNING,
        DmsExecutionJob.STATUS_COMPLETED,
        DmsExecutionJob.STATUS_PARTIAL,
    }:
        return OperationResult.failure(
            "validation_form",
            "Este job ya fue ejecutado o está en ejecución.",
        )

    job.status = DmsExecutionJob.STATUS_RUNNING
    job.job_type = DmsExecutionJob.JOB_FULL
    job.started_at = dj_timezone.now()
    job.executed_by = user
    job.error_message = ""
    job.save(
        update_fields=[
            "status",
            "job_type",
            "started_at",
            "executed_by",
            "error_message",
            "updated_at",
        ]
    )

    try:
        source, target, mappings = _load_bundle(job.version)
        processing_report = source.get("processing_report") or {}
        path = storage_service.absolute_from_stored(job.input_stored_path)
        parse_result = source_parser_service.parse_source_file(path, source)
        ok_items, errors, rows_read, capture_messages = _merge_parse_and_map(
            parse_result, mappings, target, project_id=str(project.id)
        )
        target_rows = [item["target"] for item in ok_items]

        output_bytes = target_serializer_service.serialize_rows(target_rows, target)
        pattern = (target.get("layout") or {}).get("output_filename_pattern") or "salida_{date}.txt"
        output_name = filename_service.resolve_output_filename(
            pattern,
            project=project,
            version_number=job.version.version_number,
            job_id=str(job.id),
            target_file_type=target.get("file_type_code") or "",
        )

        out_dir = storage_service.job_output_dir(project.company_id, project.id, job.id)
        reports_dir = storage_service.job_reports_dir(project.company_id, project.id, job.id)
        out_dir.mkdir(parents=True, exist_ok=True)

        output_abs = out_dir / output_name
        output_abs.write_bytes(output_bytes)

        report = execution_report_service.build_report_data(
            job_id=str(job.id),
            version_number=job.version.version_number,
            input_filename=job.input_original_filename,
            input_size=job.input_size_bytes,
            output_filename=output_name,
            rows_read=rows_read,
            rows_ok=len(target_rows),
            errors=errors,
            processing_report=processing_report,
            extra_messages=capture_messages,
        )
        primary_name, _fmt = execution_report_service.write_execution_reports(
            reports_dir,
            report,
            errors,
            processing_report,
        )
        report_rel = (
            storage_service.relative_to_media(reports_dir / primary_name)
            if primary_name
            else ""
        )

        job.output_filename = output_name
        job.output_stored_path = storage_service.relative_to_media(output_abs)
        job.output_size_bytes = len(output_bytes)
        job.report_path = report_rel
        job.rows_read = rows_read
        job.rows_ok = len(target_rows)
        job.rows_rejected = len({err["line"] for err in errors})
        job.finished_at = dj_timezone.now()
        job.status = (
            DmsExecutionJob.STATUS_PARTIAL if errors else DmsExecutionJob.STATUS_COMPLETED
        )
        job.save()
        project.save(update_fields=["updated_at"])
    except (
        source_parser_service.ParseError,
        target_serializer_service.SerializeError,
    ) as exc:
        job.status = DmsExecutionJob.STATUS_FAILED
        job.error_message = str(exc)
        job.finished_at = dj_timezone.now()
        job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        return OperationResult.failure("validation_form", str(exc))
    except Exception:
        logger.exception("run_full_job unexpected job=%s", job_id)
        job.status = DmsExecutionJob.STATUS_FAILED
        job.error_message = "Error inesperado al ejecutar."
        job.finished_at = dj_timezone.now()
        job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al ejecutar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message=(
            f"Transformación finalizada: {job.rows_ok} filas OK"
            + (f", {job.rows_rejected} rechazadas." if job.rows_rejected else ".")
        ),
        payload={
            "job": job,
            "job_id": str(job.id),
            "status": job.status,
            "rows_read": job.rows_read,
            "rows_ok": job.rows_ok,
            "rows_rejected": job.rows_rejected,
            "output_filename": job.output_filename,
            "downloads": build_download_links(project.slug, job),
        },
    )


def build_download_links(project_slug: str, job: DmsExecutionJob) -> dict:
    links = {}
    for kind in ("output", "report", "errors"):
        path_name = {
            "output": "transform_execution_download_output",
            "report": "transform_execution_download_report",
            "errors": "transform_execution_download_errors",
        }[kind]
        base = reverse(
            f"dms:{path_name}",
            kwargs={"project_slug": project_slug, "job_id": job.id},
        )
        links[kind] = f"{base}?{download_token_service.download_querystring(str(job.id), kind)}"
    return links


def list_history(project: Project) -> list[DmsExecutionJob]:
    return list(
        DmsExecutionJob.objects.filter(project=project, job_type=DmsExecutionJob.JOB_FULL)
        .exclude(status=DmsExecutionJob.STATUS_UPLOADED)
        .select_related("version", "executed_by")
        .order_by("-finished_at", "-created_at")[:100]
    )


def list_uploaded_jobs(project: Project) -> list[DmsExecutionJob]:
    return list(
        DmsExecutionJob.objects.filter(
            project=project, status=DmsExecutionJob.STATUS_UPLOADED
        )
        .select_related("version")
        .order_by("-created_at")[:50]
    )


def resolve_download_path(job: DmsExecutionJob, kind: str):
    if kind == "output":
        return job.output_stored_path, job.output_filename or "output.txt"
    if kind == "report":
        if not job.report_path:
            return "", "report.json"
        report_abs = storage_service.absolute_from_stored(job.report_path)
        return job.report_path, report_abs.name
    if kind == "errors":
        if not job.report_path:
            return "", "errors.csv"
        report_abs = storage_service.absolute_from_stored(job.report_path)
        return storage_service.relative_to_media(report_abs.parent / "errors.csv"), "errors.csv"
    return "", ""


def is_download_expired(job: DmsExecutionJob) -> bool:
    ref = job.finished_at or job.created_at
    if ref is None:
        return True
    if dj_timezone.is_naive(ref):
        ref = dj_timezone.make_aware(ref, timezone.utc)
    return dj_timezone.now() > ref + timedelta(days=7)
