"""Orquestación File Split/Merge Run — Módulo 5 (sm_run.md)."""

from __future__ import annotations

import copy
import logging
import time
import uuid
from pathlib import Path

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.constants import PRODUCTION_PREVIEW_MAX_BYTES
from apps.dms.file_intake.services import (
    detection_service,
    file_intake_persistence_service,
    storage_service,
)
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.source_profile.services.field_normalization_service import (
    normalize_fields_list,
)
from apps.dms.transform_execution.constants import DOWNLOAD_TTL
from apps.dms.transform_execution.services.source_parser_service import (
    ParseError,
    parse_source_file,
)
from apps.file_split_merge.models import SplitMergeJob
from apps.file_split_merge.rules.services import (
    split_merge_rules_catalog as catalog,
)
from apps.file_split_merge.rules.services import (
    split_merge_rules_persistence_service as rules_svc,
)
from apps.file_split_merge.run.services import sm_engine_service as engine
from apps.file_split_merge.run.services import sm_output_service as output_svc
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

RUN_MAX_BYTES = PRODUCTION_PREVIEW_MAX_BYTES
PREVIEW_ROWS = 20
ARTIFACT_TTL = DOWNLOAD_TTL
PARSE_ISSUES_UI_LIMIT = 100

MSG_KIND = "Este proyecto no es de tipo File Split/Merge."
MSG_FORBIDDEN = "No tiene permiso para ejecutar en este proyecto."
MSG_NO_PUBLISHED = "Publique una versión antes de ejecutar."
MSG_UNEXPECTED = "Ocurrió un error al ejecutar. Si persiste, contacte al administrador."
MSG_PARSE = "No se pudo leer el archivo con el perfil publicado."
MSG_PARSE_EMPTY = (
    "No se obtuvo ninguna fila válida al leer el archivo. "
    "Revise captura (inicio/fin) y el layout del perfil publicado."
)
MSG_DOWNLOAD_BAD = "Enlace de descarga inválido o expirado."
MSG_DOWNLOAD_TTL = (
    "La evidencia expiró (TTL de 7 días). Los metadatos del job siguen disponibles."
)
MSG_JOB_NOT_FOUND = "No se encontró la ejecución solicitada."
MSG_COMPLETED_SPLIT = "Partición finalizada correctamente."
MSG_COMPLETED_MERGE = "Consolidación finalizada correctamente."
MSG_PREVIEW_OK = "Vista previa generada. No se guardó archivo de salida definitivo."
MSG_FAILED = "La ejecución no pudo completarse."
MSG_SPLIT_FILES = "Split requiere exactamente un archivo de entrada."
MSG_MERGE_FILES = "Merge requiere al menos dos archivos de entrada."

STATUS_LABELS = {
    SplitMergeJob.STATUS_QUEUED: "En cola",
    SplitMergeJob.STATUS_RUNNING: "En curso",
    SplitMergeJob.STATUS_COMPLETED: "Completado",
    SplitMergeJob.STATUS_FAILED: "Fallido",
}


def source_for_sm_parse(source: dict) -> dict:
    """Perfil de lectura sin rechazo por content_type/pattern (SM ≠ Gate)."""
    adapted = copy.deepcopy(source or {})
    fields = []
    for field in adapted.get("fields") or []:
        if not isinstance(field, dict):
            continue
        item = dict(field)
        item["content_type"] = "free_text"
        item["required"] = False
        item.pop("pattern", None)
        fields.append(item)
    adapted["fields"] = fields
    return adapted


def user_can_execute(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def user_can_download(user, project: Project) -> bool:
    return user_can_execute(user, project)


def job_finished_at(job: SplitMergeJob):
    return job.finished_at or job.created_at


def is_download_expired(job: SplitMergeJob) -> bool:
    if job.dry_run:
        return True
    ref = job_finished_at(job)
    if ref is None:
        return True
    return timezone.now() > ref + ARTIFACT_TTL


def ttl_remaining_label(job: SplitMergeJob) -> str:
    if is_download_expired(job):
        return "Expirado"
    ref = job_finished_at(job)
    remaining = (ref + ARTIFACT_TTL) - timezone.now()
    days = max(0, remaining.days)
    if days >= 1:
        return f"{days} d"
    hours = max(1, int(remaining.total_seconds() // 3600))
    return f"{hours} h"


def authorize_download(user, project: Project, job: SplitMergeJob) -> OperationResult:
    if not user_can_download(user, project):
        return OperationResult.failure("forbidden", MSG_FORBIDDEN)
    if job.dry_run:
        return OperationResult.failure("validation_form", MSG_DOWNLOAD_BAD)
    if is_download_expired(job):
        return OperationResult.failure("gone", MSG_DOWNLOAD_TTL)
    return OperationResult.success()


def get_published_version(project: Project) -> DmsMappingVersion | None:
    return file_intake_persistence_service.get_published_version(project)


def _extensions_for_type(file_type_code: str) -> list[str]:
    code = (file_type_code or "").strip()
    if not code:
        return []
    try:
        from apps.dms.models import SourceFileType

        match = SourceFileType.objects.filter(code=code, is_active=True).first()
        if match and match.extensions:
            out = []
            for ext in match.extensions:
                text = str(ext).lower().strip()
                if not text:
                    continue
                if not text.startswith("."):
                    text = f".{text}"
                out.append(text)
            return out
    except Exception:
        logger.exception("extensions_for_type failed code=%s", code)
    return []


def published_source(published: DmsMappingVersion) -> dict:
    source = source_persistence_service.profile_to_dict(published.source_profile)
    source["fields"] = normalize_fields_list(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    return source


def published_sm_payload(published: DmsMappingVersion) -> dict:
    profile = published.source_profile
    raw = (profile.config or {}).get(rules_svc.CONFIG_KEY) or {}
    if not isinstance(raw, dict):
        raw = {}
    operation = (raw.get("operation") or "").strip()
    rules_raw = raw.get("rules") or []
    rules = []
    if isinstance(rules_raw, list):
        for index, item in enumerate(rules_raw):
            if not isinstance(item, dict):
                continue
            rules.append(
                {
                    "id": str(item.get("id") or ""),
                    "code": (item.get("code") or "").strip(),
                    "params": item.get("params") or {},
                    "enabled": bool(item.get("enabled", True)),
                    "sort_order": int(
                        item.get("sort_order")
                        if item.get("sort_order") is not None
                        else index
                    ),
                }
            )
    rules.sort(key=lambda r: r["sort_order"])
    return {"operation": operation, "rules": rules}


def get_run_context(user, project: Project) -> dict:
    published = get_published_version(project)
    can_execute = user_can_execute(user, project)
    ctx: dict = {
        "has_published_version": published is not None,
        "can_execute": can_execute,
        "published_version_number": published.version_number if published else None,
        "operation": "",
        "operation_label": "—",
        "is_split": False,
        "is_merge": False,
        "file_type_code": "",
        "file_type_label": "—",
        "fields_count": 0,
        "rules_enabled_count": 0,
        "allowed_extensions": [],
        "allowed_extensions_label": "—",
        "max_size_label": detection_service.human_size(RUN_MAX_BYTES),
        "preview_rows": PREVIEW_ROWS,
        "recent_jobs": [],
    }
    if published is not None:
        try:
            source = published_source(published)
            payload = published_sm_payload(published)
        except Exception:
            logger.exception("get_run_context published snapshot incomplete")
            ctx["has_published_version"] = False
            ctx["recent_jobs"] = list_recent(project, limit=8)
            return ctx
        code = (source.get("file_type_code") or "").strip()
        ext = _extensions_for_type(code)
        operation = payload.get("operation") or ""
        enabled = sum(1 for r in payload.get("rules") or [] if r.get("enabled", True))
        ctx.update(
            {
                "operation": operation,
                "operation_label": catalog.OPERATION_LABELS.get(operation, "—"),
                "is_split": operation == catalog.OPERATION_SPLIT,
                "is_merge": operation == catalog.OPERATION_MERGE,
                "file_type_code": code,
                "file_type_label": source_persistence_service.file_type_label(code),
                "fields_count": len(source.get("fields") or []),
                "rules_enabled_count": enabled,
                "allowed_extensions": ext,
                "allowed_extensions_label": ", ".join(ext) if ext else "—",
            }
        )
    ctx["recent_jobs"] = list_recent(project, limit=8)
    return ctx


def list_recent(project: Project, *, limit: int = 8) -> list[dict]:
    jobs = (
        SplitMergeJob.objects.filter(project=project)
        .exclude(status=SplitMergeJob.STATUS_RUNNING)
        .select_related("executed_by")
        .order_by("-created_at")[:limit]
    )
    return [_job_summary(job) for job in jobs]


def last_job_label(project: Project) -> str:
    job = (
        SplitMergeJob.objects.filter(project=project)
        .exclude(status=SplitMergeJob.STATUS_RUNNING)
        .order_by("-created_at")
        .first()
    )
    if job is None:
        return "—"
    label = STATUS_LABELS.get(job.status, job.status)
    inputs = job.inputs or []
    name = inputs[0].get("filename") if inputs else "archivo"
    dry = " · preview" if job.dry_run else ""
    op = job.operation or ""
    return f"{label} · {op} · {name}{dry}"


def _job_summary(job: SplitMergeJob) -> dict:
    metrics = job.metrics or {}
    inputs = job.inputs or []
    filename = inputs[0].get("filename") if inputs else "—"
    if len(inputs) > 1:
        filename = f"{filename} +{len(inputs) - 1}"
    return {
        "id": str(job.id),
        "job": job,
        "status": job.status,
        "status_label": STATUS_LABELS.get(job.status, job.status),
        "dry_run": job.dry_run,
        "operation": job.operation,
        "operation_label": catalog.OPERATION_LABELS.get(job.operation, job.operation),
        "filename": filename,
        "published_version_number": job.published_version_number,
        "parts_count": metrics.get("parts_count"),
        "rows_written": metrics.get("rows_written"),
        "created_at": job.created_at,
        "is_success": job.status == SplitMergeJob.STATUS_COMPLETED,
        "is_failed": job.status == SplitMergeJob.STATUS_FAILED,
    }


def get_job(project: Project, job_id) -> SplitMergeJob | None:
    try:
        return SplitMergeJob.objects.select_related(
            "published_version", "executed_by"
        ).get(project=project, id=job_id)
    except (SplitMergeJob.DoesNotExist, ValueError, TypeError):
        return None


def _validate_upload(uploaded_file, *, allowed_exts: list[str], label: str = "archivo"):
    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            f"Seleccione un {label}.",
            errors={"file": [f"Seleccione un {label}."]},
        )
    name = getattr(uploaded_file, "name", "") or ""
    ext = detection_service.extension_of(name)
    if allowed_exts and (not ext or ext not in allowed_exts):
        return OperationResult.failure(
            "validation_form",
            "La extensión del archivo no coincide con el perfil publicado.",
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


def _finish_failed(job: SplitMergeJob, *, message: str, error_code: str = "") -> None:
    job.status = SplitMergeJob.STATUS_FAILED
    job.error_message = message
    job.error_code = error_code
    job.finished_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "error_message",
            "error_code",
            "finished_at",
            "metrics",
            "preview",
            "outputs",
            "manifest_path",
        ]
    )


def _idempotent_existing(project: Project, idempotency_key: str | None):
    key = (idempotency_key or "").strip()
    if not key:
        return None
    return SplitMergeJob.objects.filter(project=project, idempotency_key=key).first()


def _normalize_files(files) -> list:
    if files is None:
        return []
    if isinstance(files, (list, tuple)):
        return [f for f in files if f is not None]
    # QueryDict getlist style single UploadedFile
    return [files]


@transaction.atomic
def run_sm_job(
    user,
    project: Project,
    files,
    *,
    dry_run: bool = False,
    idempotency_key: str | None = None,
    version: DmsMappingVersion | None = None,
) -> OperationResult:
    """Runner API-ready (sin request). Solo versión publicada activa."""
    if project.project_kind != Project.KIND_FILE_SPLIT_MERGE:
        return OperationResult.failure("forbidden", MSG_KIND)
    if not user_can_execute(user, project):
        return OperationResult.failure("forbidden", MSG_FORBIDDEN)

    existing = _idempotent_existing(project, idempotency_key)
    if existing is not None:
        return OperationResult.success(
            user_message=(
                MSG_COMPLETED_SPLIT
                if existing.operation == catalog.OPERATION_SPLIT
                else MSG_COMPLETED_MERGE
            )
            if existing.status == SplitMergeJob.STATUS_COMPLETED
            else MSG_FAILED,
            payload={
                "job": existing,
                "job_id": str(existing.id),
                "idempotent_replay": True,
            },
        )

    published = version or get_published_version(project)
    if published is None:
        return OperationResult.failure(
            "validation_form",
            MSG_NO_PUBLISHED,
            errors={"version": ["Se requiere una versión publicada."]},
        )
    from apps.dms.mapping.models import DmsProjectConfig

    fresh = DmsProjectConfig.objects.filter(project_id=project.id).first()
    if fresh is None or fresh.current_version_id != published.id:
        return OperationResult.failure(
            "validation_form",
            MSG_NO_PUBLISHED,
            errors={"version": ["Solo se puede ejecutar la versión publicada activa."]},
        )

    try:
        source = published_source(published)
        payload = published_sm_payload(published)
    except Exception:
        logger.exception("run_sm_job load published")
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    operation = (payload.get("operation") or "").strip()
    rules = payload.get("rules") or []
    if operation not in catalog.OPERATIONS:
        return OperationResult.failure(
            "validation_form",
            "La versión publicada no tiene operación Split/Merge.",
            errors={"operation": ["Publique de nuevo tras elegir operación."]},
        )

    file_list = _normalize_files(files)
    if operation == catalog.OPERATION_SPLIT and len(file_list) != 1:
        return OperationResult.failure(
            "validation_form",
            MSG_SPLIT_FILES,
            errors={"file": [MSG_SPLIT_FILES]},
        )
    if operation == catalog.OPERATION_MERGE and len(file_list) < 2:
        return OperationResult.failure(
            "validation_form",
            MSG_MERGE_FILES,
            errors={"file": [MSG_MERGE_FILES]},
        )

    allowed = _extensions_for_type(source.get("file_type_code") or "")
    for uploaded in file_list:
        invalid = _validate_upload(uploaded, allowed_exts=allowed)
        if invalid:
            return invalid

    job_id = uuid.uuid4()
    dest = storage_service.job_input_dir(project.company_id, project.id, job_id)
    inputs_meta = []
    stored_paths = []
    try:
        for uploaded in file_list:
            stored_path, size_bytes, content_hash = storage_service.store_upload(
                uploaded, dest, prefix_uuid=str(job_id)
            )
            stored_paths.append(stored_path)
            inputs_meta.append(
                {
                    "filename": storage_service.sanitize_filename(
                        getattr(uploaded, "name", "file")
                    ),
                    "stored_path": stored_path,
                    "size_bytes": size_bytes,
                    "content_hash": content_hash,
                    "mime": getattr(uploaded, "content_type", "") or "",
                }
            )
    except Exception:
        logger.exception("run_sm_job store failed project=%s", project.slug)
        for path in stored_paths:
            storage_service.delete_stored(path)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    key = (idempotency_key or "").strip()
    try:
        job = SplitMergeJob.objects.create(
            id=job_id,
            project=project,
            published_version=published,
            published_version_number=published.version_number,
            operation=operation,
            status=SplitMergeJob.STATUS_RUNNING,
            dry_run=bool(dry_run),
            idempotency_key=key,
            inputs=inputs_meta,
            rules_snapshot=payload,
            executed_by=user if getattr(user, "is_authenticated", False) else None,
            started_at=timezone.now(),
        )
    except IntegrityError:
        replay = _idempotent_existing(project, key)
        for path in stored_paths:
            storage_service.delete_stored(path)
        if replay is not None:
            return OperationResult.success(
                user_message=MSG_COMPLETED_SPLIT,
                payload={
                    "job": replay,
                    "job_id": str(replay.id),
                    "idempotent_replay": True,
                },
            )
        raise

    started = time.perf_counter()
    parse_source = source_for_sm_parse(source)
    field_names = [
        (f.get("name") or "").strip()
        for f in (source.get("fields") or [])
        if (f.get("name") or "").strip()
    ]
    # Preview still parses full file for accurate part counts (SM); limit only sample later
    parse_limit = None

    row_sets: list[tuple[str, list[dict]]] = []
    all_parse_errors: list = []

    try:
        for meta in inputs_meta:
            path = storage_service.absolute_from_stored(meta["stored_path"])
            parsed = parse_source_file(path, parse_source, limit=parse_limit)
            parse_errors = list(parsed.errors or [])
            all_parse_errors.extend(parse_errors)
            rows = [dict(row.data) for row in parsed.rows]
            if not rows:
                metrics = {
                    "rows_read": 0,
                    "rows_written": 0,
                    "parts_count": 0,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "dry_run": bool(dry_run),
                    "parse_errors": len(all_parse_errors),
                    "parse_issues_preview": all_parse_errors[:PARSE_ISSUES_UI_LIMIT],
                }
                job.metrics = metrics
                job.preview = {
                    "field_names": field_names,
                    "parse_issues": all_parse_errors[:PARSE_ISSUES_UI_LIMIT],
                }
                _finish_failed(
                    job, message=MSG_PARSE_EMPTY, error_code="file_sm_parse_empty"
                )
                return OperationResult.failure(
                    "file_sm_parse_empty",
                    MSG_PARSE_EMPTY,
                    job=job,
                    job_id=str(job.id),
                )
            row_sets.append((meta["filename"], rows))
    except ParseError as exc:
        logger.info("run_sm_job parse error job=%s: %s", job_id, exc)
        _finish_failed(job, message=MSG_PARSE, error_code="file_sm_parse")
        return OperationResult.failure(
            "file_sm_parse",
            MSG_PARSE,
            job=job,
            job_id=str(job.id),
        )
    except Exception:
        logger.exception("run_sm_job parse unexpected job=%s", job_id)
        _finish_failed(job, message=MSG_UNEXPECTED, error_code="unexpected")
        return OperationResult.failure(
            "unexpected",
            MSG_UNEXPECTED,
            job=job,
            job_id=str(job.id),
        )

    try:
        if operation == catalog.OPERATION_SPLIT:
            result = engine.split_rows(
                row_sets[0][1], rules, field_names=field_names
            )
        else:
            result = engine.merge_row_sets(row_sets, rules, field_names=field_names)
    except engine.SmEngineError as exc:
        logger.info("run_sm_job engine job=%s: %s", job_id, exc)
        _finish_failed(job, message=str(exc), error_code=exc.error_code)
        return OperationResult.failure(
            exc.error_code,
            str(exc),
            job=job,
            job_id=str(job.id),
        )
    except Exception:
        logger.exception("run_sm_job engine unexpected job=%s", job_id)
        _finish_failed(job, message=MSG_UNEXPECTED, error_code="unexpected")
        return OperationResult.failure(
            "unexpected",
            MSG_UNEXPECTED,
            job=job,
            job_id=str(job.id),
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    metrics = {
        **(result.metrics or {}),
        "duration_ms": duration_ms,
        "dry_run": bool(dry_run),
        "parse_errors": len(all_parse_errors),
        "parse_issues_preview": all_parse_errors[:PARSE_ISSUES_UI_LIMIT],
        "operation": operation,
    }
    if operation == catalog.OPERATION_SPLIT:
        preview = output_svc.build_split_preview(result, limit=PREVIEW_ROWS)
    else:
        preview = output_svc.build_merge_preview(
            result, source.get("fields") or [], limit=PREVIEW_ROWS
        )
    if all_parse_errors:
        preview["parse_issues"] = all_parse_errors[:PARSE_ISSUES_UI_LIMIT]
    preview["field_names"] = field_names

    outputs: list[dict] = []
    manifest_path = ""

    if not dry_run:
        try:
            if operation == catalog.OPERATION_SPLIT:
                outputs, manifest_path = output_svc.write_split_artifacts(
                    project,
                    job.id,
                    result,
                    source,
                    original_name=inputs_meta[0]["filename"],
                )
            else:
                outputs = output_svc.write_merge_artifact(
                    project,
                    job.id,
                    result,
                    source,
                    original_name=inputs_meta[0]["filename"],
                )
        except output_svc.SmOutputError as exc:
            logger.info("run_sm_job serialize error job=%s: %s", job_id, exc)
            _finish_failed(
                job, message=str(exc) or MSG_FAILED, error_code="file_sm_serialize"
            )
            return OperationResult.failure(
                "file_sm_serialize",
                MSG_FAILED,
                job=job,
                job_id=str(job.id),
            )
        except Exception:
            logger.exception("run_sm_job artifacts failed job=%s", job_id)
            _finish_failed(job, message=MSG_UNEXPECTED, error_code="unexpected")
            return OperationResult.failure(
                "unexpected",
                MSG_UNEXPECTED,
                job=job,
                job_id=str(job.id),
            )

    job.status = SplitMergeJob.STATUS_COMPLETED
    job.metrics = metrics
    job.preview = preview
    job.outputs = outputs
    job.manifest_path = manifest_path
    job.finished_at = timezone.now()
    job.save()
    project.save(update_fields=["updated_at"])

    if dry_run:
        msg = MSG_PREVIEW_OK
    elif operation == catalog.OPERATION_SPLIT:
        msg = MSG_COMPLETED_SPLIT
    else:
        msg = MSG_COMPLETED_MERGE

    return OperationResult.success(
        user_message=msg,
        payload={
            "job": job,
            "job_id": str(job.id),
            "status": job.status,
            "metrics": metrics,
            "artifact_refs": {"outputs": outputs, "manifest": manifest_path},
            "dry_run": bool(dry_run),
        },
    )


def build_job_view(project: Project, job: SplitMergeJob) -> dict:
    metrics = job.metrics or {}
    preview = job.preview or {}
    expired = is_download_expired(job)
    can_offer = not job.dry_run and not expired and job.status == SplitMergeJob.STATUS_COMPLETED
    outputs = job.outputs or []
    by_kind = {o.get("kind"): o for o in outputs if isinstance(o, dict)}

    download_urls = {}
    if can_offer:
        for item in outputs:
            kind = item.get("kind") or ""
            if not kind:
                continue
            download_urls[kind] = reverse(
                "file_split_merge:run_download",
                kwargs={
                    "project_slug": project.slug,
                    "job_id": job.id,
                    "kind": kind,
                },
            )

    inputs = job.inputs or []
    input_names = [i.get("filename") or "—" for i in inputs]
    preview_fields = preview.get("field_names") or []

    merge_matrix = []
    if preview.get("kind") == "merge":
        for row in preview.get("rows") or []:
            if not isinstance(row, dict):
                continue
            merge_matrix.append([row.get(name, "") for name in preview_fields])

    return {
        "id": str(job.id),
        "status": job.status,
        "status_label": STATUS_LABELS.get(job.status, job.status),
        "dry_run": job.dry_run,
        "operation": job.operation,
        "operation_label": catalog.OPERATION_LABELS.get(job.operation, job.operation),
        "is_split": job.operation == catalog.OPERATION_SPLIT,
        "is_merge": job.operation == catalog.OPERATION_MERGE,
        "is_success": job.status == SplitMergeJob.STATUS_COMPLETED,
        "is_failed": job.status == SplitMergeJob.STATUS_FAILED,
        "published_version_number": job.published_version_number,
        "input_filenames": input_names,
        "input_label": ", ".join(input_names) if input_names else "—",
        "error_message": job.error_message,
        "error_code": job.error_code,
        "metrics": metrics,
        "preview": preview,
        "preview_fields": preview_fields,
        "preview_parts": preview.get("parts") or [],
        "preview_merge_rows": merge_matrix,
        "parse_issues": preview.get("parse_issues")
        or (metrics.get("parse_issues_preview") or []),
        "parse_errors_count": int(metrics.get("parse_errors") or 0),
        "outputs": outputs,
        "by_kind": by_kind,
        "download_urls": download_urls,
        "can_offer_downloads": can_offer,
        "is_expired": expired,
        "ttl_label": ttl_remaining_label(job),
        "ttl_days": ARTIFACT_TTL.days,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "duration_ms": metrics.get("duration_ms"),
    }


def resolve_download(job: SplitMergeJob, kind: str) -> tuple[Path, str] | None:
    """Return (absolute_path, download_filename) or None."""
    if kind == "input":
        inputs = job.inputs or []
        if not inputs:
            return None
        meta = inputs[0]
        path = storage_service.absolute_from_stored(meta.get("stored_path") or "")
        if not path.exists():
            return None
        return path, meta.get("filename") or path.name

    if kind == "manifest" and job.manifest_path:
        path = storage_service.absolute_from_stored(job.manifest_path)
        if path.exists():
            return path, "manifest.json"

    for item in job.outputs or []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == kind:
            stored = item.get("stored_path") or ""
            path = storage_service.absolute_from_stored(stored)
            if path.exists():
                return path, item.get("filename") or path.name
    return None
