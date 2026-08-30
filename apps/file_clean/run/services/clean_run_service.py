"""Orquestación Clean Run — Módulo 5 (clean_run.md)."""

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
from apps.file_clean.models import CleanJob
from apps.file_clean.rules.services import clean_rules_persistence_service as rules_svc
from apps.file_clean.run.services import clean_engine_service as engine
from apps.file_clean.run.services import clean_output_service as output_svc
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

RUN_MAX_BYTES = PRODUCTION_PREVIEW_MAX_BYTES
PREVIEW_ROWS = 20
ARTIFACT_TTL = DOWNLOAD_TTL

MSG_KIND = "Este proyecto no es de tipo File Clean."
MSG_FORBIDDEN = "No tiene permiso para ejecutar limpiezas en este proyecto."
MSG_NO_PUBLISHED = "Publique una versión antes de ejecutar la limpieza."
MSG_UNEXPECTED = "Ocurrió un error al limpiar. Si persiste, contacte al administrador."
MSG_PARSE = "No se pudo leer el archivo con el perfil publicado."
MSG_PARSE_EMPTY = (
    "No se obtuvo ninguna fila válida al leer el archivo. "
    "Revise captura (inicio/fin) y el layout del perfil publicado."
)
MSG_PARSE_EMPTY_DELIMITER = (
    "No se obtuvo ninguna fila válida: el delimitador del perfil no coincide "
    "con el archivo (p. ej. perfil con «;» y CSV con comas «,»). "
    "En Perfil → Paso 4 cambie el delimitador, guarde, publique de nuevo y reintente."
)
MSG_RULE_RUNTIME = "Error al aplicar una regla de limpieza. Revise la definición publicada."
MSG_DOWNLOAD_BAD = "Enlace de descarga inválido o expirado."
MSG_DOWNLOAD_GONE = "Archivo expirado."
MSG_DOWNLOAD_TTL = "La evidencia expiró (TTL de 7 días). Los metadatos del job siguen disponibles."
MSG_JOB_NOT_FOUND = "No se encontró la ejecución solicitada."
MSG_COMPLETED = "Limpieza finalizada correctamente."
MSG_PREVIEW_OK = "Vista previa generada. No se guardó archivo de salida definitivo."
MSG_FAILED = "La limpieza no pudo completarse."

PARSE_ISSUES_UI_LIMIT = 100


def source_for_clean_parse(source: dict) -> dict:
    """Perfil de lectura sin rechazo por content_type/pattern (Clean ≠ Gate).

    File Clean lee filas y aplica reglas; la tipificación estricta es de File Gate.
    Se conserva layout, captura y posiciones.
    """
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

STATUS_LABELS = {
    CleanJob.STATUS_QUEUED: "En cola",
    CleanJob.STATUS_RUNNING: "En curso",
    CleanJob.STATUS_COMPLETED: "Completado",
    CleanJob.STATUS_FAILED: "Fallido",
}


def user_can_execute(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return ProjectMembership.role_can_execute(membership.role)


def user_can_download(user, project: Project) -> bool:
    return user_can_execute(user, project)


def job_finished_at(job: CleanJob):
    return job.finished_at or job.created_at


def is_download_expired(job: CleanJob) -> bool:
    if job.dry_run:
        return True
    ref = job_finished_at(job)
    if ref is None:
        return True
    return timezone.now() > ref + ARTIFACT_TTL


def ttl_remaining_label(job: CleanJob) -> str:
    if is_download_expired(job):
        return "Expirado"
    ref = job_finished_at(job)
    remaining = (ref + ARTIFACT_TTL) - timezone.now()
    days = max(0, remaining.days)
    if days >= 1:
        return f"{days} d"
    hours = max(1, int(remaining.total_seconds() // 3600))
    return f"{hours} h"


def authorize_download(user, project: Project, job: CleanJob) -> OperationResult:
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


def published_rules(published: DmsMappingVersion) -> list[dict]:
    profile = published.source_profile
    raw = (profile.config or {}).get(rules_svc.CONFIG_KEY) or []
    if not isinstance(raw, list):
        return []
    rules = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        rules.append(
            {
                "id": str(item.get("id") or ""),
                "code": (item.get("code") or "").strip(),
                "field_name": (item.get("field_name") or None),
                "params": item.get("params") or {},
                "enabled": bool(item.get("enabled", True)),
                "sort_order": int(
                    item.get("sort_order") if item.get("sort_order") is not None else index
                ),
            }
        )
    rules.sort(key=lambda r: r["sort_order"])
    return rules


def get_run_context(user, project: Project) -> dict:
    published = get_published_version(project)
    can_execute = user_can_execute(user, project)
    ctx: dict = {
        "has_published_version": published is not None,
        "can_execute": can_execute,
        "published_version_number": published.version_number if published else None,
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
            rules = published_rules(published)
        except Exception:
            logger.exception("get_run_context published snapshot incomplete")
            ctx["has_published_version"] = False
            ctx["recent_jobs"] = list_recent(project, limit=8)
            return ctx
        code = (source.get("file_type_code") or "").strip()
        ext = _extensions_for_type(code)
        enabled = sum(1 for r in rules if r.get("enabled", True))
        ctx.update(
            {
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
        CleanJob.objects.filter(project=project)
        .exclude(status=CleanJob.STATUS_RUNNING)
        .select_related("executed_by")
        .order_by("-created_at")[:limit]
    )
    return [_job_summary(job) for job in jobs]


def last_job_label(project: Project) -> str:
    job = (
        CleanJob.objects.filter(project=project)
        .exclude(status=CleanJob.STATUS_RUNNING)
        .order_by("-created_at")
        .first()
    )
    if job is None:
        return "—"
    label = STATUS_LABELS.get(job.status, job.status)
    name = job.input_original_filename or "archivo"
    dry = " · preview" if job.dry_run else ""
    return f"{label} · {name}{dry}"


def _job_summary(job: CleanJob) -> dict:
    metrics = job.metrics or {}
    return {
        "id": str(job.id),
        "job": job,
        "status": job.status,
        "status_label": STATUS_LABELS.get(job.status, job.status),
        "dry_run": job.dry_run,
        "filename": job.input_original_filename or "—",
        "published_version_number": job.published_version_number,
        "rows_read": metrics.get("rows_read"),
        "rows_written": metrics.get("rows_written"),
        "cells_changed": metrics.get("cells_changed"),
        "created_at": job.created_at,
        "is_success": job.status == CleanJob.STATUS_COMPLETED,
        "is_failed": job.status == CleanJob.STATUS_FAILED,
    }


def get_job(project: Project, job_id) -> CleanJob | None:
    try:
        return CleanJob.objects.select_related("published_version", "executed_by").get(
            project=project, id=job_id
        )
    except (CleanJob.DoesNotExist, ValueError, TypeError):
        return None


def _validate_upload(uploaded_file, *, allowed_exts: list[str]) -> OperationResult | None:
    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            "Seleccione un archivo para limpiar.",
            errors={"file": ["Seleccione un archivo."]},
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


def _finish_failed(job: CleanJob, *, message: str, error_code: str = "") -> None:
    job.status = CleanJob.STATUS_FAILED
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
        ]
    )


def _empty_parse_message(parse_errors: list) -> str:
    if any(
        (err.get("code") or "") == "DELIMITER_MISMATCH"
        for err in (parse_errors or [])
        if isinstance(err, dict)
    ):
        return MSG_PARSE_EMPTY_DELIMITER
    return MSG_PARSE_EMPTY


def _idempotent_existing(
    project: Project, idempotency_key: str | None
) -> CleanJob | None:
    key = (idempotency_key or "").strip()
    if not key:
        return None
    return CleanJob.objects.filter(project=project, idempotency_key=key).first()


@transaction.atomic
def run_clean_job(
    user,
    project: Project,
    version: DmsMappingVersion | None,
    uploaded_file,
    *,
    dry_run: bool = False,
    idempotency_key: str | None = None,
    require_membership: bool = True,
) -> OperationResult:
    """
    Runner API-ready (sin request).
    Solo versión publicada en ejecución productiva.
    """
    if project.project_kind != Project.KIND_FILE_CLEAN:
        return OperationResult.failure("forbidden", MSG_KIND)
    if require_membership and not user_can_execute(user, project):
        return OperationResult.failure("forbidden", MSG_FORBIDDEN)

    existing = _idempotent_existing(project, idempotency_key)
    if existing is not None:
        return OperationResult.success(
            user_message=MSG_COMPLETED if existing.status == CleanJob.STATUS_COMPLETED else MSG_FAILED,
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
    config = getattr(project, "dms_config", None)
    if config is None or config.current_version_id != published.id:
        return OperationResult.failure(
            "validation_form",
            MSG_NO_PUBLISHED,
            errors={"version": ["Solo se puede ejecutar la versión publicada activa."]},
        )

    try:
        source = published_source(published)
        rules = published_rules(published)
    except Exception:
        logger.exception("run_clean_job load published")
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    if not any(r.get("enabled", True) for r in rules):
        return OperationResult.failure(
            "validation_form",
            "La versión publicada no tiene reglas de limpieza habilitadas.",
            errors={"rules": ["Habilite al menos una regla y vuelva a publicar."]},
        )

    allowed = _extensions_for_type(source.get("file_type_code") or "")
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
        logger.exception("run_clean_job store failed project=%s", project.slug)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    if size_bytes == 0:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            "El archivo está vacío.",
            errors={"file": ["El archivo no puede estar vacío."]},
        )

    key = (idempotency_key or "").strip()
    try:
        job = CleanJob.objects.create(
            id=job_id,
            project=project,
            published_version=published,
            published_version_number=published.version_number,
            status=CleanJob.STATUS_RUNNING,
            dry_run=bool(dry_run),
            idempotency_key=key,
            input_original_filename=storage_service.sanitize_filename(
                getattr(uploaded_file, "name", "file")
            ),
            input_stored_path=stored_path,
            input_size_bytes=size_bytes,
            input_content_hash=content_hash,
            input_mime_type=getattr(uploaded_file, "content_type", "") or "",
            rules_snapshot=rules,
            executed_by=user if getattr(user, "is_authenticated", False) else None,
            started_at=timezone.now(),
        )
    except IntegrityError:
        replay = _idempotent_existing(project, key)
        if replay is not None:
            storage_service.delete_stored(stored_path)
            return OperationResult.success(
                user_message=MSG_COMPLETED,
                payload={
                    "job": replay,
                    "job_id": str(replay.id),
                    "idempotent_replay": True,
                },
            )
        raise

    started = time.perf_counter()
    path = storage_service.absolute_from_stored(stored_path)
    parse_limit = PREVIEW_ROWS if dry_run else None
    parse_source = source_for_clean_parse(source)

    try:
        parsed = parse_source_file(path, parse_source, limit=parse_limit)
    except ParseError as exc:
        logger.info("run_clean_job parse error job=%s: %s", job_id, exc)
        _finish_failed(job, message=MSG_PARSE, error_code="file_clean_parse")
        return OperationResult.failure(
            "file_clean_parse",
            MSG_PARSE,
            job=job,
            job_id=str(job.id),
        )
    except Exception:
        logger.exception("run_clean_job parse unexpected job=%s", job_id)
        _finish_failed(job, message=MSG_UNEXPECTED, error_code="unexpected")
        return OperationResult.failure(
            "unexpected",
            MSG_UNEXPECTED,
            job=job,
            job_id=str(job.id),
        )

    parse_errors = list(parsed.errors or [])
    before_rows = [dict(row.data) for row in parsed.rows]
    if not before_rows:
        metrics = {
            "rows_read": 0,
            "rows_written": 0,
            "cells_changed": 0,
            "dedupe_count": 0,
            "by_code": {},
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "dry_run": bool(dry_run),
            "parse_errors": len(parse_errors),
            "parse_issues_preview": parse_errors[:PARSE_ISSUES_UI_LIMIT],
        }
        job.metrics = metrics
        job.preview = {
            "field_names": [
                (f.get("name") or "").strip()
                for f in (source.get("fields") or [])
                if (f.get("name") or "").strip()
            ],
            "parse_issues": parse_errors[:PARSE_ISSUES_UI_LIMIT],
        }
        empty_msg = _empty_parse_message(parse_errors)
        _finish_failed(job, message=empty_msg, error_code="file_clean_parse_empty")
        return OperationResult.failure(
            "file_clean_parse_empty",
            empty_msg,
            job=job,
            job_id=str(job.id),
        )

    try:
        result = engine.apply_rules(before_rows, rules)
    except ValueError:
        logger.exception("run_clean_job rule runtime job=%s", job_id)
        _finish_failed(
            job, message=MSG_RULE_RUNTIME, error_code="file_clean_rule_runtime"
        )
        return OperationResult.failure(
            "file_clean_rule_runtime",
            MSG_RULE_RUNTIME,
            job=job,
            job_id=str(job.id),
        )
    except Exception:
        logger.exception("run_clean_job engine unexpected job=%s", job_id)
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
        "parse_errors": len(parse_errors),
        "parse_issues_preview": parse_errors[:PARSE_ISSUES_UI_LIMIT],
    }
    preview = output_svc.build_preview(
        before_rows,
        result.rows,
        source.get("fields") or [],
        limit=PREVIEW_ROWS,
    )
    if parse_errors:
        preview["parse_issues"] = parse_errors[:PARSE_ISSUES_UI_LIMIT]

    output_path = ""
    output_name = ""
    output_size = 0
    output_hash = ""
    change_log_path = ""

    if not dry_run:
        try:
            output_bytes = output_svc.serialize_clean_rows(result.rows, source, rules)
            output_name = output_svc.default_output_filename(
                job.input_original_filename,
                source.get("file_type_code") or "",
            )
            output_path, output_size, output_hash = output_svc.write_output_file(
                project, job.id, output_bytes, output_name
            )
            change_log_path = output_svc.write_change_log_artifacts(
                project, job.id, result.change_log
            )
        except output_svc.CleanOutputError as exc:
            logger.info("run_clean_job serialize error job=%s: %s", job_id, exc)
            _finish_failed(job, message=str(exc) or MSG_FAILED, error_code="file_clean_serialize")
            return OperationResult.failure(
                "file_clean_serialize",
                MSG_FAILED,
                job=job,
                job_id=str(job.id),
            )
        except Exception:
            logger.exception("run_clean_job artifacts failed job=%s", job_id)
            _finish_failed(job, message=MSG_UNEXPECTED, error_code="unexpected")
            return OperationResult.failure(
                "unexpected",
                MSG_UNEXPECTED,
                job=job,
                job_id=str(job.id),
            )

    job.status = CleanJob.STATUS_COMPLETED
    job.metrics = metrics
    job.preview = preview
    job.output_filename = output_name
    job.output_stored_path = output_path
    job.output_size_bytes = output_size
    job.output_content_hash = output_hash
    job.change_log_path = change_log_path
    job.finished_at = timezone.now()
    job.save()
    project.save(update_fields=["updated_at"])

    return OperationResult.success(
        user_message=MSG_PREVIEW_OK if dry_run else MSG_COMPLETED,
        payload={
            "job": job,
            "job_id": str(job.id),
            "status": job.status,
            "metrics": metrics,
            "artifact_refs": {
                "input": job.input_stored_path,
                "output": job.output_stored_path,
                "change_log": job.change_log_path,
            },
            "dry_run": bool(dry_run),
        },
    )


def build_job_view(project: Project, job: CleanJob) -> dict:
    metrics = job.metrics or {}
    preview = job.preview or {}
    expired = is_download_expired(job)
    can_offer = not job.dry_run and not expired
    downloads = {
        "output": bool(job.output_stored_path) and can_offer,
        "change_log": bool(job.change_log_path) and can_offer,
        "change_log_csv": bool(job.change_log_path) and can_offer,
    }
    by_code = metrics.get("by_code") or {}
    by_code_rows = [
        {"code": code, "count": count}
        for code, count in sorted(by_code.items(), key=lambda item: (-item[1], item[0]))
    ]
    preview_fields = preview.get("field_names") or []

    def _matrix(rows: list) -> list[list]:
        matrix = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            matrix.append([row.get(name, "") for name in preview_fields])
        return matrix

    return {
        "id": str(job.id),
        "status": job.status,
        "status_label": STATUS_LABELS.get(job.status, job.status),
        "dry_run": job.dry_run,
        "is_success": job.status == CleanJob.STATUS_COMPLETED,
        "is_failed": job.status == CleanJob.STATUS_FAILED,
        "published_version_number": job.published_version_number,
        "input_filename": job.input_original_filename,
        "input_size_label": detection_service.human_size(job.input_size_bytes),
        "input_hash_short": (job.input_content_hash or "")[:12],
        "output_filename": job.output_filename or "—",
        "output_size_label": (
            detection_service.human_size(job.output_size_bytes)
            if job.output_size_bytes
            else "—"
        ),
        "output_hash_short": (job.output_content_hash or "")[:12],
        "error_message": job.error_message,
        "error_code": job.error_code,
        "metrics": metrics,
        "by_code_rows": by_code_rows,
        "preview": preview,
        "preview_fields": preview_fields,
        "preview_before_rows": _matrix(preview.get("before") or []),
        "preview_after_rows": _matrix(preview.get("after") or []),
        "parse_issues": preview.get("parse_issues")
        or (metrics.get("parse_issues_preview") or []),
        "parse_errors_count": int(metrics.get("parse_errors") or 0),
        "downloads": downloads,
        "is_expired": expired,
        "ttl_label": ttl_remaining_label(job),
        "ttl_days": ARTIFACT_TTL.days,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "duration_ms": metrics.get("duration_ms"),
        "download_urls": {
            "output": reverse(
                "file_clean:run_download",
                kwargs={
                    "project_slug": project.slug,
                    "job_id": job.id,
                    "kind": "output",
                },
            )
            if downloads["output"]
            else "",
            "change_log": reverse(
                "file_clean:run_download",
                kwargs={
                    "project_slug": project.slug,
                    "job_id": job.id,
                    "kind": "change_log",
                },
            )
            if downloads["change_log"]
            else "",
            "change_log_csv": reverse(
                "file_clean:run_download",
                kwargs={
                    "project_slug": project.slug,
                    "job_id": job.id,
                    "kind": "change_log_csv",
                },
            )
            if downloads["change_log_csv"]
            else "",
        },
    }


def resolve_download(job: CleanJob, kind: str) -> tuple[str, str]:
    """Devuelve (path relativo MEDIA, filename) o ("", "")."""
    if job.dry_run:
        return "", ""
    if kind == "output":
        if not job.output_stored_path:
            return "", ""
        return job.output_stored_path, job.output_filename or "clean_output"
    if kind in {"change_log", "change_log_json"}:
        if not job.change_log_path:
            return "", ""
        return job.change_log_path, "change_log.json"
    if kind == "change_log_csv":
        if not job.change_log_path:
            return "", ""
        abs_json = storage_service.absolute_from_stored(job.change_log_path)
        csv_abs = abs_json.parent / "change_log.csv"
        if not csv_abs.is_file():
            return "", ""
        return storage_service.relative_to_media(csv_abs), "change_log.csv"
    return "", ""


def resolve_download_path(job: CleanJob, kind: str) -> Path | None:
    stored, _name = resolve_download(job, kind)
    if not stored:
        return None
    path = storage_service.absolute_from_stored(stored)
    if not path.is_file():
        return None
    return path
