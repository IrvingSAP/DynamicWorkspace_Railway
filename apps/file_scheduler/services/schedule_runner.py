"""Resuelve artifact en storage del tenant e invoca el runner de la app destino."""

from __future__ import annotations

import logging
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.models import DmsExecutionJob, DmsSampleFile
from apps.dms.file_intake.services import storage_service
from apps.file_clean.models import CleanJob
from apps.file_scheduler.models import Schedule
from apps.file_scheduler.services import schedule_errors as err
from apps.projects.models import Project

logger = logging.getLogger(__name__)

RUNNABLE_JOB_KINDS = frozenset({"file_clean", "file_gate", "dms"})
TRIGGERED_BY = "system:scheduler"

MSG_ARTIFACT_NOT_FOUND = err.MSG_ARTIFACT_NOT_FOUND
MSG_RUNNER_UNSUPPORTED = err.MSG_RUNNER_UNSUPPORTED


def normalize_artifact_hash(ref: str) -> str:
    raw = (ref or "").strip()
    if raw.lower().startswith("sha256:"):
        raw = raw[7:].strip()
    hex_chars = "".join(ch for ch in raw.lower() if ch in "0123456789abcdef")
    return hex_chars[:64]


def wrap_stored_upload(stored_path: str, filename: str = "") -> SimpleUploadedFile | None:
    if not stored_path:
        return None
    absolute = storage_service.absolute_from_stored(stored_path)
    if not absolute.is_file():
        return None
    name = (filename or absolute.name or "file").strip() or "file"
    if "_" in name and len(name.split("_", 1)[0]) in {32, 36}:
        name = name.split("_", 1)[1] or name
    return SimpleUploadedFile(name, absolute.read_bytes())


def resolve_artifact(company_id, ref: str) -> dict | None:
    digest = normalize_artifact_hash(ref)
    if len(digest) < 16:
        return None
    exact = len(digest) == 64

    def match(qs, field: str):
        if exact:
            return qs.filter(**{field: digest})
        return qs.filter(**{f"{field}__istartswith": digest})

    clean_in = (
        match(
            CleanJob.objects.filter(project__company_id=company_id).exclude(
                input_stored_path=""
            ),
            "input_content_hash",
        )
        .order_by("-created_at")
        .first()
    )
    if clean_in is not None:
        return _row(
            clean_in.input_stored_path,
            clean_in.input_original_filename,
            clean_in.input_content_hash,
        )

    clean_out = (
        match(
            CleanJob.objects.filter(project__company_id=company_id).exclude(
                output_stored_path=""
            ),
            "output_content_hash",
        )
        .order_by("-created_at")
        .first()
    )
    if clean_out is not None:
        return _row(
            clean_out.output_stored_path,
            clean_out.output_filename or clean_out.input_original_filename,
            clean_out.output_content_hash,
        )

    dms = (
        match(
            DmsExecutionJob.objects.filter(project__company_id=company_id).exclude(
                input_stored_path=""
            ),
            "input_content_hash",
        )
        .order_by("-created_at")
        .first()
    )
    if dms is not None:
        return _row(dms.input_stored_path, dms.input_original_filename, dms.input_content_hash)

    sample = (
        match(
            DmsSampleFile.objects.filter(project__company_id=company_id).exclude(
                stored_path=""
            ),
            "content_hash",
        )
        .order_by("-created_at")
        .first()
    )
    if sample is not None:
        return _row(sample.stored_path, sample.original_filename, sample.content_hash)

    try:
        from apps.file_watch.models import WatchBatch

        batch = (
            match(
                WatchBatch.objects.filter(company_id=company_id).exclude(storage_key=""),
                "content_hash",
            )
            .order_by("-created_at")
            .first()
        )
        if batch is not None:
            return _row(batch.storage_key, batch.original_filename, batch.content_hash)
    except Exception:
        logger.exception("resolve_artifact WatchBatch lookup failed")
    return None


def _row(stored_path: str, filename: str, content_hash: str) -> dict | None:
    absolute = storage_service.absolute_from_stored(stored_path)
    if not absolute.is_file():
        return None
    return {
        "stored_path": stored_path,
        "filename": filename or Path(stored_path).name,
        "content_hash": content_hash or "",
    }


def stamp_trigger(job, *, schedule: Schedule, trigger_source: str, correlation: str, slot_iso: str) -> None:
    payload = {
        "trigger_source": trigger_source,
        "schedule_id": str(schedule.id),
        "scheduled_for": slot_iso,
        "correlation_id": correlation,
        "triggered_by": TRIGGERED_BY,
    }
    suggestions = getattr(job, "input_suggestions", None)
    if isinstance(suggestions, dict):
        merged = dict(suggestions)
        merged.update(payload)
        job.input_suggestions = merged
        job.save(update_fields=["input_suggestions", "updated_at"] if hasattr(job, "updated_at") else ["input_suggestions"])
        return
    metrics = dict(getattr(job, "metrics", None) or {})
    metrics["scheduler"] = payload
    job.metrics = metrics
    fields = ["metrics"]
    if hasattr(job, "updated_at"):
        fields.append("updated_at")
    job.save(update_fields=fields)


def run_job_kind(
    schedule: Schedule,
    project: Project,
    upload,
    *,
    trigger_source: str,
    correlation: str,
    slot_iso: str,
) -> OperationResult:
    kind = (schedule.target_kind or "").strip()
    actor = schedule.owner
    if kind not in RUNNABLE_JOB_KINDS:
        return OperationResult.failure("schedule_runner_unsupported", MSG_RUNNER_UNSUPPORTED)
    if kind == "file_clean":
        from apps.file_clean.run.services import clean_run_service

        result = clean_run_service.run_clean_job(
            actor,
            project,
            None,
            upload,
            require_membership=False,
            idempotency_key=f"schedule:{schedule.id}:{slot_iso}",
        )
    elif kind == "file_gate":
        from apps.file_gate.run.services import validation_run_service

        result = validation_run_service.validate_and_run(
            actor, project, upload, require_membership=False
        )
    else:
        result = _run_dms(actor, project, upload)
    job = (result.payload or {}).get("job") if result.payload else None
    if job is None:
        return result
    try:
        stamp_trigger(
            job,
            schedule=schedule,
            trigger_source=trigger_source,
            correlation=correlation,
            slot_iso=slot_iso,
        )
    except Exception:
        logger.exception("stamp_trigger failed job=%s", getattr(job, "pk", ""))
    return result


def _run_dms(actor, project: Project, upload) -> OperationResult:
    from apps.dms.transform_execution.services import execution_service
    from apps.dms.file_intake.services import file_intake_persistence_service

    stored = file_intake_persistence_service.upload_production(
        actor, project, upload, require_membership=False
    )
    if not stored.ok:
        return stored
    job = (stored.payload or {}).get("job")
    if job is None:
        return stored
    ran = execution_service.run_full_job(
        actor, project, job.id, require_membership=False
    )
    if not ran.ok:
        return ran
    refreshed = DmsExecutionJob.objects.filter(pk=job.id).first() or job
    return OperationResult.success(
        ran.user_message or stored.user_message,
        payload={"job": refreshed, "job_id": str(refreshed.id)},
    )
