"""Orquestación Match Run — Módulo 5 (match_run.md)."""

from __future__ import annotations

import csv
import io
import json
import logging
import time
import uuid

from django.db import transaction
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
from apps.dms.transform_execution.services.source_parser_service import (
    ParseError,
    parse_source_file,
)
from apps.file_match.bridge.services import match_bridge_service
from apps.file_match.models import FileMatchJob, FileMatchRules, FileMatchSourceB
from apps.file_match.profile_b.services import profile_b_persistence_service
from apps.file_match.rules.services import match_rules_persistence_service
from apps.file_match.services import match_engine
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

RUN_MAX_BYTES = PRODUCTION_PREVIEW_MAX_BYTES

VERDICT_LABELS = {
    FileMatchJob.VERDICT_PASSED: "Cuadra",
    FileMatchJob.VERDICT_FAILED: "No cuadra",
    FileMatchJob.VERDICT_PARTIAL: "Parcial",
}

VERDICT_TONE = {
    FileMatchJob.VERDICT_PASSED: "passed",
    FileMatchJob.VERDICT_FAILED: "failed",
    FileMatchJob.VERDICT_PARTIAL: "partial",
}


def user_can_execute(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def user_can_download_detail(user, project: Project) -> bool:
    """CO no descarga filas de negocio."""
    return user_can_execute(user, project)


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
            return [str(ext).lower() for ext in match.extensions]
    except Exception:
        logger.exception("extensions_for_type failed code=%s", code)
    return []


def _published_side_a(published: DmsMappingVersion) -> dict:
    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list,
    )

    source = source_persistence_service.profile_to_dict(published.source_profile)
    source["fields"] = normalize_fields_list(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    return source


def _published_side_b(published: DmsMappingVersion) -> dict:
    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list,
    )

    profile = published.match_source_b
    source = profile_b_persistence_service.profile_to_dict(profile)
    source["fields"] = normalize_fields_list(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    return source


def _published_rules(published: DmsMappingVersion) -> dict:
    rules_obj = published.match_rules
    return match_rules_persistence_service.normalize_rules_dict(rules_obj.rules or {})


def get_run_context(user, project: Project) -> dict:
    published = get_published_version(project)
    can_execute = user_can_execute(user, project)
    ctx: dict = {
        "has_published_version": published is not None,
        "can_execute": can_execute,
        "published_version_number": published.version_number if published else None,
        "file_type_a_code": "",
        "file_type_a_label": "—",
        "file_type_b_code": "",
        "file_type_b_label": "—",
        "fields_a_count": 0,
        "fields_b_count": 0,
        "key_count": 0,
        "compare_count": 0,
        "key_summary": "—",
        "allowed_extensions_a": [],
        "allowed_extensions_b": [],
        "allowed_extensions_a_label": "—",
        "allowed_extensions_b_label": "—",
        "max_size_label": detection_service.human_size(RUN_MAX_BYTES),
        "recent_jobs": [],
    }

    if published is not None:
        try:
            source_a = _published_side_a(published)
            source_b = _published_side_b(published)
            rules = _published_rules(published)
        except (FileMatchSourceB.DoesNotExist, FileMatchRules.DoesNotExist, Exception):
            logger.exception("get_run_context published snapshot incomplete")
            ctx["has_published_version"] = False
            ctx["recent_jobs"] = list_recent(project, limit=8)
            return ctx

        code_a = (source_a.get("file_type_code") or "").strip()
        code_b = (source_b.get("file_type_code") or "").strip()
        ext_a = _extensions_for_type(code_a)
        ext_b = _extensions_for_type(code_b)
        key = rules.get("key") or []
        compare = rules.get("compare") or []
        key_summary = " · ".join(
            f"{(p.get('a') or '?')}↔{(p.get('b') or '?')}" for p in key[:3]
        ) or "—"
        ctx.update(
            {
                "file_type_a_code": code_a,
                "file_type_a_label": source_persistence_service.file_type_label(code_a),
                "file_type_b_code": code_b,
                "file_type_b_label": source_persistence_service.file_type_label(code_b),
                "fields_a_count": len(source_a.get("fields") or []),
                "fields_b_count": len(source_b.get("fields") or []),
                "key_count": len(key),
                "compare_count": len(compare),
                "key_summary": key_summary,
                "allowed_extensions_a": ext_a,
                "allowed_extensions_b": ext_b,
                "allowed_extensions_a_label": ", ".join(ext_a) if ext_a else "—",
                "allowed_extensions_b_label": ", ".join(ext_b) if ext_b else "—",
            }
        )

    ctx["recent_jobs"] = list_recent(project, limit=8)
    ctx["bridge"] = match_bridge_service.get_run_banner(project)
    return ctx


def list_recent(project: Project, *, limit: int = 8) -> list[dict]:
    jobs = (
        FileMatchJob.objects.filter(project=project)
        .exclude(status=FileMatchJob.STATUS_RUNNING)
        .select_related("executed_by")
        .order_by("-created_at")[:limit]
    )
    return [_job_summary(job) for job in jobs]


def _job_summary(job: FileMatchJob) -> dict:
    return {
        "job": job,
        "id": str(job.id),
        "verdict": job.verdict,
        "verdict_label": VERDICT_LABELS.get(job.verdict, job.verdict or job.status),
        "verdict_tone": VERDICT_TONE.get(job.verdict, "failed"),
        "file_a_name": job.file_a_name,
        "file_b_name": job.file_b_name,
        "match_pct": (job.metrics or {}).get("match_pct"),
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "published_version_number": job.published_version_number,
    }


def get_job(project: Project, job_id) -> FileMatchJob | None:
    return (
        FileMatchJob.objects.select_related("published_version", "executed_by")
        .filter(project=project, id=job_id)
        .first()
    )


def build_job_view(project: Project, job: FileMatchJob) -> dict:
    metrics = job.metrics or {}
    return {
        "job": job,
        "id": str(job.id),
        "verdict": job.verdict,
        "verdict_label": VERDICT_LABELS.get(job.verdict, job.verdict or "—"),
        "verdict_tone": VERDICT_TONE.get(job.verdict, "failed"),
        "is_success": job.verdict == FileMatchJob.VERDICT_PASSED,
        "is_partial": job.verdict == FileMatchJob.VERDICT_PARTIAL,
        "metrics": metrics,
        "detail_preview": job.detail_preview or [],
        "file_a_name": job.file_a_name,
        "file_b_name": job.file_b_name,
        "file_a_hash": job.file_a_hash,
        "file_b_hash": job.file_b_hash,
        "file_a_size_label": detection_service.human_size(job.file_a_size_bytes or 0),
        "file_b_size_label": detection_service.human_size(job.file_b_size_bytes or 0),
        "published_version_number": job.published_version_number,
        "error_message": job.error_message,
        "duration_ms": metrics.get("duration_ms"),
        "downloads": build_download_links(project.slug, job) if job.report_path else {},
    }


def build_download_links(project_slug: str, job: FileMatchJob) -> dict:
    links = {}
    for kind in ("report", "diff"):
        links[kind] = reverse(
            "file_match:run_download",
            kwargs={"project_slug": project_slug, "job_id": job.id, "kind": kind},
        )
    return links


def _validate_upload(uploaded_file, *, side: str, allowed_exts: list[str]) -> OperationResult | None:
    label = f"archivo {side}"
    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            f"Seleccione el {label}.",
            errors={f"file_{side.lower()}": [f"Seleccione el {label}."]},
        )
    name = getattr(uploaded_file, "name", "") or ""
    ext = detection_service.extension_of(name)
    if allowed_exts and (not ext or ext not in allowed_exts):
        return OperationResult.failure(
            "validation_form",
            f"La extensión del {label} no coincide con el perfil publicado.",
            errors={
                f"file_{side.lower()}": [
                    f"Extensión «{ext or 'sin extensión'}» no permitida para {side}. "
                    f"Permitidas: {', '.join(allowed_exts)}."
                ]
            },
        )
    size = getattr(uploaded_file, "size", None)
    if size is not None and size == 0:
        return OperationResult.failure(
            "validation_form",
            f"El {label} está vacío.",
            errors={f"file_{side.lower()}": ["El archivo no puede estar vacío."]},
        )
    if size is not None and size > RUN_MAX_BYTES:
        return OperationResult.failure(
            "validation_form",
            f"El {label} supera el límite de {detection_service.human_size(RUN_MAX_BYTES)}.",
            errors={
                f"file_{side.lower()}": [
                    f"Tamaño máximo: {detection_service.human_size(RUN_MAX_BYTES)}."
                ]
            },
        )
    return None


def _write_reports(project: Project, job: FileMatchJob, *, engine_result, rules: dict) -> str:
    reports_dir = storage_service.job_reports_dir(project.company_id, project.id, job.id)
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "job_id": str(job.id),
        "verdict": engine_result.verdict,
        "published_version": job.published_version_number,
        "files": {
            "a": {
                "name": job.file_a_name,
                "size_bytes": job.file_a_size_bytes,
                "hash": job.file_a_hash,
            },
            "b": {
                "name": job.file_b_name,
                "size_bytes": job.file_b_size_bytes,
                "hash": job.file_b_hash,
            },
        },
        "rules_snapshot": rules,
        "metrics": engine_result.metrics,
        "messages": engine_result.messages,
        "detail": engine_result.detail,
    }
    json_abs = reports_dir / "match_report.json"
    json_abs.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["bucket", "key", "field_a", "field_b", "value_a", "value_b", "note"])
    for item in engine_result.detail:
        bucket = item.get("bucket") or ""
        key = item.get("key") or ""
        diffs = item.get("diffs") or []
        if not diffs:
            note = ""
            if bucket == "duplicate_key":
                note = f"count_a={item.get('count_a')} count_b={item.get('count_b')}"
            writer.writerow([bucket, key, "", "", "", "", note])
        else:
            for diff in diffs:
                writer.writerow(
                    [
                        bucket,
                        key,
                        diff.get("a", ""),
                        diff.get("b", ""),
                        diff.get("value_a", ""),
                        diff.get("value_b", ""),
                        "",
                    ]
                )
    csv_abs = reports_dir / "match_diff.csv"
    csv_abs.write_text(buffer.getvalue(), encoding="utf-8")

    return storage_service.relative_to_media(json_abs)


def _parse_side(path, source: dict, *, side: str) -> tuple[list[dict], bool, OperationResult | None]:
    try:
        result = parse_source_file(path, source, limit=match_engine.ROW_HARD_LIMIT + 1)
    except ParseError as exc:
        return [], False, OperationResult.failure(
            "validation_form",
            f"No se pudo leer el archivo {side}. Revise el perfil publicado.",
            errors={f"file_{side.lower()}": [str(exc) or "Error de parseo."]},
        )
    except Exception:
        logger.exception("parse_side unexpected side=%s", side)
        return [], False, OperationResult.failure(
            "unexpected",
            f"Ocurrió un error al leer el archivo {side}. Si persiste, contacte al administrador.",
        )

    truncated = result.rows_read > match_engine.ROW_HARD_LIMIT or len(result.rows) > match_engine.ROW_HARD_LIMIT
    rows = [row.data for row in result.rows[: match_engine.ROW_HARD_LIMIT]]
    if not rows and result.errors:
        return [], False, OperationResult.failure(
            "validation_form",
            f"No se pudo leer el archivo {side}. Revise el perfil publicado.",
            errors={
                f"file_{side.lower()}": [
                    (result.errors[0].get("message") if isinstance(result.errors[0], dict) else str(result.errors[0]))
                    or "Sin filas válidas."
                ]
            },
        )
    return rows, truncated, None


@transaction.atomic
def match_and_run(user, project: Project, file_a, file_b) -> OperationResult:
    if project.project_kind != Project.KIND_FILE_MATCH:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE MATCH.",
        )
    if not user_can_execute(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para ejecutar conciliaciones en este proyecto.",
        )

    published = get_published_version(project)
    if published is None:
        return OperationResult.failure(
            "validation_form",
            "Publique una definición antes de conciliar.",
            errors={"version": ["Se requiere una versión publicada."]},
        )

    try:
        source_a = _published_side_a(published)
        source_b = _published_side_b(published)
        rules = _published_rules(published)
    except (FileMatchSourceB.DoesNotExist, FileMatchRules.DoesNotExist):
        return OperationResult.failure(
            "validation_form",
            "La versión publicada está incompleta (falta perfil B o reglas).",
        )
    except Exception:
        logger.exception("match_and_run load published")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al conciliar. Si persiste, contacte al administrador.",
        )

    if not (rules.get("key") or []):
        return OperationResult.failure(
            "validation_form",
            "La definición publicada no tiene clave de cruce.",
        )

    ext_a = _extensions_for_type(source_a.get("file_type_code") or "")
    ext_b = _extensions_for_type(source_b.get("file_type_code") or "")
    err_a = _validate_upload(file_a, side="A", allowed_exts=ext_a)
    if err_a:
        return err_a
    err_b = _validate_upload(file_b, side="B", allowed_exts=ext_b)
    if err_b:
        return err_b

    job_id = uuid.uuid4()
    dest = storage_service.job_input_dir(project.company_id, project.id, job_id)
    try:
        path_a, size_a, hash_a = storage_service.store_upload(
            file_a, dest, prefix_uuid=f"{job_id}-a"
        )
        path_b, size_b, hash_b = storage_service.store_upload(
            file_b, dest, prefix_uuid=f"{job_id}-b"
        )
    except Exception:
        logger.exception("match_and_run store failed project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    gate_check = match_bridge_service.precheck_sides(
        project, hash_a=hash_a, hash_b=hash_b
    )
    if not gate_check.ok:
        return OperationResult.failure(
            gate_check.error_code or "gate_blocked",
            gate_check.user_message,
            **(gate_check.payload or {}),
        )

    job = FileMatchJob.objects.create(
        id=job_id,
        project=project,
        published_version=published,
        published_version_number=published.version_number,
        status=FileMatchJob.STATUS_RUNNING,
        file_a_name=getattr(file_a, "name", "") or "",
        file_a_path=path_a,
        file_a_size_bytes=size_a,
        file_a_hash=hash_a,
        file_b_name=getattr(file_b, "name", "") or "",
        file_b_path=path_b,
        file_b_size_bytes=size_b,
        file_b_hash=hash_b,
        rules_snapshot=rules,
        executed_by=user if getattr(user, "is_authenticated", False) else None,
        metrics=(
            {"file_gate_check": gate_check.payload.get("seal") or {}}
            if not gate_check.payload.get("skipped")
            else {}
        ),
    )

    started = time.perf_counter()
    abs_a = storage_service.absolute_from_stored(path_a)
    abs_b = storage_service.absolute_from_stored(path_b)

    rows_a, trunc_a, parse_err_a = _parse_side(abs_a, source_a, side="A")
    if parse_err_a is not None:
        job.status = FileMatchJob.STATUS_FAILED
        job.verdict = FileMatchJob.VERDICT_FAILED
        job.error_message = parse_err_a.user_message or ""
        job.finished_at = timezone.now()
        job.metrics = {"duration_ms": int((time.perf_counter() - started) * 1000)}
        job.save()
        return parse_err_a

    rows_b, trunc_b, parse_err_b = _parse_side(abs_b, source_b, side="B")
    if parse_err_b is not None:
        job.status = FileMatchJob.STATUS_FAILED
        job.verdict = FileMatchJob.VERDICT_FAILED
        job.error_message = parse_err_b.user_message or ""
        job.finished_at = timezone.now()
        job.metrics = {"duration_ms": int((time.perf_counter() - started) * 1000)}
        job.save()
        return parse_err_b

    try:
        engine_result = match_engine.run_match(
            rows_a, rows_b, rules, truncated=trunc_a or trunc_b
        )
        engine_result.metrics["duration_ms"] = int((time.perf_counter() - started) * 1000)
        report_path = _write_reports(project, job, engine_result=engine_result, rules=rules)

        if engine_result.verdict == "passed":
            job.status = FileMatchJob.STATUS_COMPLETED
            job.verdict = FileMatchJob.VERDICT_PASSED
        elif engine_result.verdict == "partial":
            job.status = FileMatchJob.STATUS_PARTIAL
            job.verdict = FileMatchJob.VERDICT_PARTIAL
        else:
            job.status = FileMatchJob.STATUS_FAILED
            job.verdict = FileMatchJob.VERDICT_FAILED

        metrics = dict(engine_result.metrics or {})
        gate_seal = (job.metrics or {}).get("file_gate_check")
        if gate_seal:
            metrics["file_gate_check"] = gate_seal
        job.metrics = metrics
        job.detail_preview = engine_result.detail
        job.report_path = report_path
        job.finished_at = timezone.now()
        if engine_result.messages:
            job.error_message = " · ".join(engine_result.messages)
        job.save()
    except Exception:
        logger.exception("match_and_run engine failed project=%s", project.slug)
        job.status = FileMatchJob.STATUS_FAILED
        job.verdict = FileMatchJob.VERDICT_FAILED
        job.error_message = "Ocurrió un error al conciliar."
        job.finished_at = timezone.now()
        job.save()
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al conciliar. Si persiste, contacte al administrador.",
        )

    project.save(update_fields=["updated_at"])
    label = VERDICT_LABELS.get(job.verdict, job.verdict)
    return OperationResult.success(
        user_message=f"Conciliación completada: {label}.",
        payload={"job": job},
    )


def resolve_download_path(job: FileMatchJob, kind: str):
    if not job.report_path:
        return None
    reports_dir = storage_service.absolute_from_stored(job.report_path).parent
    if kind == "report":
        path = reports_dir / "match_report.json"
    elif kind == "diff":
        path = reports_dir / "match_diff.csv"
    else:
        return None
    if not path.is_file():
        return None
    return path
