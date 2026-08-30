from __future__ import annotations

import logging
from types import SimpleNamespace

from django.db import IntegrityError

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import file_intake_persistence_service
from apps.dms.transform_execution.services import execution_service
from apps.file_gate.run.services import validation_engine_service as gate_engine
from apps.file_gate.run.services import validation_run_service
from apps.file_match.run.services import match_run_service
from apps.file_clean.run.services import clean_run_service
from apps.file_split_merge.run.services import sm_run_service
from apps.structure_scout.detect.services import detect_pattern_service
from apps.structure_scout.sample.services import sample_upload_service
from apps.platform_api.models import ApiClient, ApiIdempotencyRecord
from apps.platform_api.services import contract_service, job_audit_service, process_security_service
from apps.platform_api.services.bearer_auth import AuthFailure, require_scopes
from apps.file_pipeline.models import PipelineDefinition, PipelineRun
from apps.file_pipeline.services import pipeline_run_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)

MSG_KIND_MVP = "En esta fase se puede ejecutar file_gate, dms, reverse, file_match, structure_scout, file_clean, file_split, file_merge o file_pipeline."
MSG_KIND_MISMATCH = "El kind no coincide con el tipo de proyecto."
MSG_UNEXPECTED = "Ocurrió un error al ejecutar. Si persiste, contacte al administrador."
MSG_GATE_OK = "Validación Gate finalizada."
MSG_PIPE_OK = "Transformación FilePipe finalizada."
MSG_REVERSE_OK = "Generación Reverse Studio finalizada."
MSG_MATCH_OK = "Conciliación File Match finalizada."
MSG_MATCH_WAIT = "file_match solo admite wait=sync en esta fase."
MSG_SCOUT_OK = "Exploración Structure Scout finalizada."
MSG_SCOUT_WAIT = "structure_scout solo admite wait=sync en esta fase."
MSG_CLEAN_OK = "Limpieza File Clean finalizada."
MSG_CLEAN_WAIT = "file_clean solo admite wait=sync en esta fase."
MSG_SPLIT_OK = "Partición File Split finalizada."
MSG_MERGE_OK = "Consolidación File Merge finalizada."
MSG_SM_WAIT = "file_split y file_merge solo admiten wait=sync en esta fase."
MSG_PIPELINE_OK = "Corrida de pipeline finalizada."
MSG_DRY_RUN_OK = "Dry-run finalizado. No se generó salida de producción."
MSG_ASYNC_OK = "Job encolado. Consulte el detalle del job para el estado."
MSG_IDEMPOTENCY_CONFLICT = "Idempotency-Key ya usada con otra entrada. Use una key nueva."
MSG_REPLAY = "Respuesta reutilizada (misma Idempotency-Key)."
MSG_PIPELINE_INACTIVE = "El pipeline no está activo o no tiene versión publicada."
MSG_PIPELINE_STEP_PERM = "No tiene permiso para ejecutar uno de los proyectos de paso."

MVP_KINDS = {
    contract_service.KIND_GATE,
    contract_service.KIND_PIPE,
    contract_service.KIND_REVERSE,
    contract_service.KIND_MATCH,
    contract_service.KIND_SCOUT,
    contract_service.KIND_CLEAN,
    contract_service.KIND_SPLIT,
    contract_service.KIND_MERGE,
    contract_service.KIND_PIPELINE,
}
KIND_TO_PROJECT = {
    contract_service.KIND_GATE: Project.KIND_FILE_GATE,
    contract_service.KIND_PIPE: Project.KIND_DMS,
    contract_service.KIND_REVERSE: Project.KIND_REVERSE,
    contract_service.KIND_MATCH: Project.KIND_FILE_MATCH,
    contract_service.KIND_SCOUT: Project.KIND_STRUCTURE_SCOUT,
    contract_service.KIND_CLEAN: Project.KIND_FILE_CLEAN,
    contract_service.KIND_SPLIT: Project.KIND_FILE_SPLIT_MERGE,
    contract_service.KIND_MERGE: Project.KIND_FILE_SPLIT_MERGE,
}


def _fail(error_code: str, user_message: str, *, http_status: int, errors: dict | None = None):
    return OperationResult.failure(
        error_code,
        user_message,
        errors=errors,
        http_status=http_status,
    )


def _first_file(posted: dict):
    items = (posted.get("_files") or {}).get("file") or []
    return items[0] if items else None


def _slot_file(posted: dict, slot: str):
    items = (posted.get("_files") or {}).get(slot) or []
    return items[0] if items else None


def _list_files(posted: dict, slot: str) -> list:
    files_map = posted.get("_files") or {}
    return list(files_map.get(slot) or files_map.get(f"{slot}[]") or [])


def _validate_upload_slot(client: ApiClient, upload, field: str) -> OperationResult:
    security = process_security_service.validate_upload(
        filename=getattr(upload, "name", "") or "",
        size_bytes=getattr(upload, "size", 0) or 0,
        company=client.company,
    )
    if security.ok:
        return security
    errors = dict(security.errors or {})
    if "file" in errors and field != "file":
        errors[field] = errors.pop("file")
    return _fail(
        security.error_code or "validation_form",
        security.user_message,
        http_status=400,
        errors=errors,
    )


def _read_hash(upload) -> str:
    raw = b""
    if upload is not None and hasattr(upload, "read"):
        raw = upload.read() or b""
        if hasattr(upload, "seek"):
            upload.seek(0)
    return process_security_service.hash_bytes(raw) if raw else ""


def _resolve_project(client: ApiClient, slug: str, kind: str) -> OperationResult:
    project = (
        Project.objects.filter(company=client.company, slug=slug, is_archived=False)
        .select_related("owner", "company")
        .first()
    )
    if project is None:
        return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
    expected = KIND_TO_PROJECT.get(kind)
    if expected and project.project_kind != expected:
        return _fail(
            "validation_form",
            MSG_KIND_MISMATCH,
            http_status=400,
            errors={"kind": [MSG_KIND_MISMATCH]},
        )
    return OperationResult.success("", project=project)


def _actor(client: ApiClient, project: Project):
    return client.created_by or project.owner


def _stamp_api(job, client: ApiClient, parsed: dict) -> None:
    job_audit_service.stamp_job_suggestions(job, client, parsed)


def _request_hash(parsed: dict, content_hash: str) -> str:
    body = (
        f"{content_hash}:{parsed['kind']}:{parsed.get('project_slug') or ''}:"
        f"{parsed.get('pipeline_id') or ''}:"
        f"{int(bool(parsed.get('dry_run')))}:{parsed['wait']}"
    )
    return process_security_service.idempotency_fingerprint(
        parsed.get("idempotency_key") or "",
        body,
    )


def _lookup_idempotency(client: ApiClient, key: str, request_hash: str) -> OperationResult | None:
    if not key:
        return None
    existing = ApiIdempotencyRecord.objects.filter(client=client, key=key).first()
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        return _fail(
            "idempotency_conflict",
            MSG_IDEMPOTENCY_CONFLICT,
            http_status=409,
            errors={"Idempotency-Key": [MSG_IDEMPOTENCY_CONFLICT]},
        )
    return OperationResult.success(
        existing.user_message or MSG_REPLAY,
        envelope=existing.envelope,
        http_status=existing.http_status,
        replay=True,
    )


def _store_idempotency(
    client: ApiClient,
    parsed: dict,
    request_hash: str,
    *,
    job,
    envelope: dict,
    user_message: str,
    http_status: int,
) -> None:
    key = parsed.get("idempotency_key") or ""
    if not key:
        return
    try:
        ApiIdempotencyRecord.objects.create(
            company=client.company,
            client=client,
            key=key,
            request_hash=request_hash,
            job_id=job.id,
            envelope=envelope,
            user_message=user_message[:240],
            http_status=http_status,
        )
    except IntegrityError:
        logger.info("idempotency race client=%s key=%s", client.pk, key)


def _map_runner_failure(result: OperationResult) -> OperationResult:
    if result.error_code == "validation_form" and result.errors and "version" in result.errors:
        return _fail(
            "unpublished",
            process_security_service.MSG_UNPUBLISHED,
            http_status=409,
            errors=result.errors,
        )
    if result.error_code == "forbidden":
        return _fail(
            "insufficient_scope",
            result.user_message,
            http_status=403,
            errors=result.errors,
        )
    if result.error_code == "not_found":
        return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
    if result.error_code == "validation_form":
        return _fail(
            "validation_form",
            result.user_message,
            http_status=400,
            errors=result.errors,
        )
    logger.exception("api jobs/run runner failed code=%s", result.error_code)
    return _fail("unexpected", MSG_UNEXPECTED, http_status=500)


def _gate_errors(job) -> list[dict]:
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    items = []
    for issue in gate.get("issues_preview") or []:
        items.append(
            contract_service.error_item(
                row=issue.get("line"),
                field=str(issue.get("field") or ""),
                code=str(issue.get("code") or ""),
                message=str(issue.get("message") or ""),
            )
        )
    return items


def _gate_verdict(job) -> str:
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    status = gate.get("status")
    if status in {gate_engine.STATUS_PASSED, gate_engine.STATUS_PASSED_WITH_WARNINGS}:
        return contract_service.GATE_ACCEPTED
    return contract_service.GATE_REJECTED


def _machine_status(job) -> str:
    status = job.status
    if status in {
        getattr(job, "STATUS_COMPLETED", "completed"),
        getattr(job, "STATUS_PARTIAL", "partial"),
    }:
        return contract_service.STATUS_COMPLETED
    if status == getattr(job, "STATUS_CANCELLED", "cancelled"):
        return contract_service.STATUS_CANCELLED
    if status == getattr(job, "STATUS_FAILED", "failed"):
        return contract_service.STATUS_FAILED
    if status == getattr(job, "STATUS_RUNNING", "running"):
        return contract_service.STATUS_RUNNING
    return contract_service.STATUS_QUEUED


def _artifacts(job) -> dict:
    job_id = str(job.id)
    artifacts: dict[str, str] = {}
    report = getattr(job, "report_path", "") or getattr(job, "change_log_path", "") or getattr(job, "manifest_path", "")
    output = getattr(job, "output_stored_path", "") or getattr(job, "output_stored_path", "")
    if not output:
        outputs = getattr(job, "outputs", None) or []
        if isinstance(outputs, list) and len(outputs) == 1:
            output = (outputs[0] or {}).get("stored_path") or ""
    if report:
        artifacts["report_url"] = f"/api/v1/jobs/{job_id}/report"
    if output:
        artifacts["output_url"] = f"/api/v1/jobs/{job_id}/output"
    return artifacts


def _envelope(*, job, parsed: dict, kind: str, content_hash: str, ok: bool, summary: dict, errors: list, extra_fields: dict | None = None):
    version_label = "published"
    version = getattr(job, "version", None) or getattr(job, "published_version", None)
    if version is not None:
        version_label = f"v{getattr(version, 'version_number', version)}"
    elif getattr(job, "published_version_number", None):
        version_label = f"v{job.published_version_number}"
    extra = {}
    if parsed.get("dry_run"):
        extra["dry_run"] = True
    if parsed.get("retry_of_job_id"):
        extra["retry_of_job_id"] = parsed["retry_of_job_id"]
    extra.update(extra_fields or {})
    if "audit" not in extra:
        extra["audit"] = job_audit_service.job_audit_payload(job)
    return contract_service.envelope(
        ok=ok,
        job_id=str(job.id),
        kind=kind,
        status=_machine_status(job),
        wait=parsed["wait"],
        project_slug=parsed.get("project_slug"),
        pipeline_id=parsed.get("pipeline_id") or extra.get("pipeline_id"),
        pipeline_run_id=extra.get("pipeline_run_id"),
        version=version_label,
        summary=summary,
        errors=errors,
        artifacts=_artifacts(job),
        content_hash=content_hash or getattr(job, "input_content_hash", None) or None,
        steps=extra.get("steps"),
        extra={k: v for k, v in extra.items() if k not in {"pipeline_id", "pipeline_run_id", "steps"}} or None,
    )


def _queue_job(actor, project, upload, client: ApiClient, parsed: dict):
    uploaded = file_intake_persistence_service.upload_production(
        actor, project, upload, require_membership=False
    )
    if not uploaded.ok:
        return uploaded
    job = uploaded.payload["job"]
    job.status = DmsExecutionJob.STATUS_QUEUED
    if parsed.get("dry_run"):
        job.job_type = DmsExecutionJob.JOB_PREVIEW
    job.save(update_fields=["status", "job_type", "updated_at"])
    _stamp_api(job, client, parsed)
    return OperationResult.success("", job=job)


def _apply_pipe_dry_run(job, preview: OperationResult):
    payload = preview.payload or {}
    job.job_type = DmsExecutionJob.JOB_PREVIEW
    job.status = DmsExecutionJob.STATUS_COMPLETED
    job.rows_read = int(payload.get("rows_read") or 0)
    job.rows_ok = int(payload.get("rows_ok") or 0)
    job.rows_rejected = int(payload.get("rows_rejected") or 0)
    job.save(
        update_fields=["job_type", "status", "rows_read", "rows_ok", "rows_rejected", "updated_at"]
    )
    return job


def _run_sync(kind: str, actor, project, upload, client: ApiClient, parsed: dict):
    if kind == contract_service.KIND_GATE:
        runner = validation_run_service.validate_and_run(
            actor, project, upload, require_membership=False
        )
        if not runner.ok:
            return runner
        job = runner.payload.get("job")
        _stamp_api(job, client, parsed)
        return OperationResult.success("", job=job)

    uploaded = file_intake_persistence_service.upload_production(
        actor, project, upload, require_membership=False
    )
    if not uploaded.ok:
        return uploaded
    job = uploaded.payload["job"]
    _stamp_api(job, client, parsed)
    if parsed.get("dry_run"):
        preview = execution_service.dry_run_job(
            actor, project, job.id, require_membership=False
        )
        if not preview.ok:
            return preview
        job = _apply_pipe_dry_run(job, preview)
        _stamp_api(job, client, parsed)
        return OperationResult.success("", job=job)
    runner = execution_service.run_full_job(
        actor, project, job.id, require_membership=False
    )
    if not runner.ok:
        return runner
    job = runner.payload.get("job")
    _stamp_api(job, client, parsed)
    return OperationResult.success("", job=job)


def _run_match(actor, project, file_a, file_b, client: ApiClient, parsed: dict):
    runner = match_run_service.match_and_run(
        actor, project, file_a, file_b, require_membership=False
    )
    if not runner.ok:
        return runner
    job = runner.payload.get("job")
    _stamp_api(job, client, parsed)
    return OperationResult.success("", job=job)


def _match_summary(job) -> dict:
    metrics = dict(job.metrics or {})
    metrics.pop("api", None)
    summary = {
        "verdict": getattr(job, "verdict", "") or "",
        "rows_a": metrics.get("rows_a"),
        "rows_b": metrics.get("rows_b"),
        "keys_total": metrics.get("keys_total"),
        "matched": metrics.get("matched"),
        "match_pct": metrics.get("match_pct"),
    }
    return {key: value for key, value in summary.items() if value is not None or key == "verdict"}


def _scout_job_view(state):
    failed = state.status == getattr(state, "STATUS_FAILED", "failed")
    sample = getattr(state, "sample", None)
    snapshot = dict(state.suggestions_snapshot or {})
    return SimpleNamespace(
        id=state.id,
        status="failed" if failed else "completed",
        STATUS_COMPLETED="completed",
        STATUS_PARTIAL="partial",
        STATUS_FAILED="failed",
        STATUS_RUNNING="running",
        STATUS_CANCELLED="cancelled",
        input_suggestions=snapshot.get("api") or {},
        metrics=snapshot,
        report_path="",
        output_stored_path="",
        input_content_hash=getattr(sample, "content_hash", "") or "",
        input_original_filename=getattr(sample, "original_filename", "") or "",
        input_size_bytes=getattr(sample, "size_bytes", 0) or 0,
        version=None,
        created_at=getattr(state, "created_at", None),
        started_at=None,
        finished_at=getattr(state, "updated_at", None),
        file_type_code=state.file_type_code,
        encoding_code=state.encoding_code,
        line_ending_code=state.line_ending_code,
        delimiter=state.delimiter,
        has_header=state.has_header,
        header_row=state.header_row,
        confidence=state.confidence,
        detection_status=state.status,
        sample_id=str(state.sample_id) if getattr(state, "sample_id", None) else None,
        notes=state.notes or "",
        rows_read=0,
        rows_ok=0,
        rows_rejected=0,
    )


def _run_scout(actor, project, upload, client: ApiClient, parsed: dict):
    uploaded = sample_upload_service.upload_sample(
        actor, project, upload, require_membership=False
    )
    if not uploaded.ok:
        return uploaded
    detected = detect_pattern_service.rerun_detection(
        actor, project, require_membership=False
    )
    if not detected.ok:
        return detected
    state = detected.payload.get("state")
    if state is None:
        return _fail("unexpected", MSG_UNEXPECTED, http_status=500)
    _stamp_api(state, client, parsed)
    job = _scout_job_view(state)
    return OperationResult.success("", job=job)


def _scout_summary(job) -> dict:
    summary = {
        "file_type_code": getattr(job, "file_type_code", "") or "",
        "encoding_code": getattr(job, "encoding_code", "") or "",
        "delimiter": getattr(job, "delimiter", "") or "",
        "has_header": getattr(job, "has_header", None),
        "confidence": getattr(job, "confidence", "") or "",
        "detection_status": getattr(job, "detection_status", "") or "",
        "sample_id": getattr(job, "sample_id", None),
    }
    return {key: value for key, value in summary.items() if value not in (None, "")}


def _run_clean(actor, project, upload, client: ApiClient, parsed: dict):
    runner = clean_run_service.run_clean_job(
        actor,
        project,
        None,
        upload,
        dry_run=bool(parsed.get("dry_run")),
        idempotency_key=parsed.get("idempotency_key") or None,
        require_membership=False,
    )
    job = (runner.payload or {}).get("job")
    if job is None:
        return runner
    _stamp_api(job, client, parsed)
    return OperationResult.success(runner.user_message or "", job=job)


def _clean_summary(job) -> dict:
    metrics = dict(job.metrics or {})
    metrics.pop("api", None)
    summary = {
        "dry_run": bool(getattr(job, "dry_run", False) or metrics.get("dry_run")),
        "rows_read": metrics.get("rows_read"),
        "rows_written": metrics.get("rows_written"),
        "cells_changed": metrics.get("cells_changed"),
        "dedupe_count": metrics.get("dedupe_count"),
        "error_code": getattr(job, "error_code", "") or "",
    }
    return {key: value for key, value in summary.items() if value not in (None, "")}


def _run_sm(kind: str, actor, project, files, client: ApiClient, parsed: dict):
    expected = "split" if kind == contract_service.KIND_SPLIT else "merge"
    runner = sm_run_service.run_sm_job(
        actor,
        project,
        files,
        dry_run=bool(parsed.get("dry_run")),
        idempotency_key=parsed.get("idempotency_key") or None,
        require_membership=False,
        expected_operation=expected,
    )
    job = (runner.payload or {}).get("job")
    if job is None:
        return runner
    _stamp_api(job, client, parsed)
    return OperationResult.success(runner.user_message or "", job=job)


def _sm_summary(job) -> dict:
    metrics = dict(job.metrics or {})
    metrics.pop("api", None)
    outputs = getattr(job, "outputs", None) or []
    summary = {
        "operation": getattr(job, "operation", "") or "",
        "dry_run": bool(getattr(job, "dry_run", False) or metrics.get("dry_run")),
        "files_in": len(getattr(job, "inputs", None) or []),
        "files_out": len(outputs) if isinstance(outputs, list) else metrics.get("files_out"),
        "rows_read": metrics.get("rows_read"),
        "error_code": getattr(job, "error_code", "") or "",
    }
    return {key: value for key, value in summary.items() if value not in (None, "")}


def _sync_message(kind: str, parsed: dict) -> str:
    if parsed.get("dry_run"):
        return MSG_DRY_RUN_OK
    if kind == contract_service.KIND_REVERSE:
        return MSG_REVERSE_OK
    if kind == contract_service.KIND_MATCH:
        return MSG_MATCH_OK
    if kind == contract_service.KIND_SCOUT:
        return MSG_SCOUT_OK
    if kind == contract_service.KIND_CLEAN:
        return MSG_CLEAN_OK
    if kind == contract_service.KIND_SPLIT:
        return MSG_SPLIT_OK
    if kind == contract_service.KIND_MERGE:
        return MSG_MERGE_OK
    return MSG_PIPE_OK


def pipeline_steps(run: PipelineRun) -> list[dict]:
    rows = []
    for step in run.steps.all():
        rows.append(
            {
                "order": step.order,
                "kind": step.kind,
                "label": step.label,
                "status": step.status,
                "project_slug": step.project_slug,
                "job_id": step.app_job_id or None,
                "app_job_id": step.app_job_id or None,
                "message": step.user_message,
            }
        )
    return rows


def serialize_pipeline_run(run: PipelineRun, parsed: dict | None = None, *, content_hash: str = "") -> dict:
    parsed = parsed or {
        "wait": contract_service.WAIT_ASYNC,
        "project_slug": None,
        "pipeline_id": run.pipeline.slug,
        "dry_run": bool(run.dry_run),
    }
    steps = pipeline_steps(run)
    ok = run.status == run.STATUS_COMPLETED
    errors = []
    if run.status == run.STATUS_FAILED and run.error_message:
        errors.append(
            contract_service.error_item(
                row=run.failed_step_order,
                field="",
                code="step_failed",
                message=run.error_message,
            )
        )
    summary = {
        "pipeline_slug": run.pipeline.slug,
        "failed_step_order": run.failed_step_order,
        "duration_ms": run.duration_ms,
        "steps_total": len(steps),
        "dry_run": bool(run.dry_run),
    }
    extra_fields = {
        "pipeline_id": run.pipeline.slug,
        "pipeline_run_id": str(run.id),
        "steps": steps,
        "trigger_source": run.trigger_source,
        "audit": job_audit_service.pipeline_audit_payload(run),
    }
    return _envelope(
        job=run,
        parsed=parsed,
        kind=contract_service.KIND_PIPELINE,
        content_hash=content_hash or run.input_sha256 or "",
        ok=ok,
        summary=summary,
        errors=errors,
        extra_fields=extra_fields,
    )


def _map_pipeline_failure(result: OperationResult) -> OperationResult:
    run = (result.payload or {}).get("run")
    if run is not None:
        return result
    message = result.user_message
    if result.error_code == "forbidden":
        status = 403
        code = "forbidden"
        if message == pipeline_run_service.MSG_NO_STEP_PERM:
            message = MSG_PIPELINE_STEP_PERM
    elif result.user_message in {
        pipeline_run_service.MSG_NO_VERSION,
        pipeline_run_service.MSG_NOT_ACTIVE,
    }:
        status = 409
        code = "unpublished"
        message = MSG_PIPELINE_INACTIVE
    else:
        return _map_runner_failure(result)
    return _fail(code, message, http_status=status)


def _run_pipeline(client: ApiClient, posted: dict, parsed: dict, upload, content_hash: str) -> OperationResult:
    slug = parsed.get("pipeline_id") or ""
    pipeline = PipelineDefinition.objects.filter(
        company=client.company, slug=slug
    ).select_related("owner", "current_version").first()
    if pipeline is None:
        return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
    actor = client.created_by or pipeline.owner
    try:
        runner = pipeline_run_service.start_run(
            actor,
            pipeline,
            upload,
            dry_run=bool(parsed.get("dry_run")),
            require_membership=False,
            trigger_source=PipelineRun.TRIGGER_API,
            correlation_id=parsed.get("correlation_id") or "",
            idempotency_key=parsed.get("idempotency_key") or "",
            api_client_label=client.code,
            api_client_id=str(client.pk),
            client_ip=parsed.get("client_ip") or "",
            user_agent=parsed.get("user_agent") or "",
        )
    except Exception:
        logger.exception("api pipeline run failed slug=%s", slug)
        return _fail("unexpected", MSG_UNEXPECTED, http_status=500)
    run = (runner.payload or {}).get("run")
    if not runner.ok and run is None:
        return _map_pipeline_failure(runner)
    if run is None:
        return _fail("unexpected", MSG_UNEXPECTED, http_status=500)
    body = serialize_pipeline_run(run, parsed, content_hash=content_hash)
    http_status = contract_service.http_status_for(
        wait=parsed["wait"],
        status=_machine_status(run),
    )
    message = MSG_DRY_RUN_OK if parsed.get("dry_run") else MSG_PIPELINE_OK
    if run.status == run.STATUS_FAILED:
        message = run.error_message or message
    _store_idempotency(
        client,
        parsed,
        _request_hash(parsed, content_hash),
        job=run,
        envelope=body,
        user_message=message,
        http_status=http_status,
    )
    from apps.platform_api.services import webhook_service

    webhook_service.notify_from_envelope(client, body)
    return OperationResult.success(message, envelope=body, http_status=http_status)


def run_job(client: ApiClient, posted: dict) -> OperationResult:
    parsed_result = contract_service.parse_run_request(posted, require_files=True)
    if not parsed_result.ok:
        return _fail(
            parsed_result.error_code or "validation_form",
            parsed_result.user_message,
            http_status=400,
            errors=parsed_result.errors,
        )
    parsed = parsed_result.payload["parsed"]
    parsed["correlation_id"] = job_audit_service.ensure_correlation_id(
        parsed.get("correlation_id")
    )
    kind = parsed["kind"]
    if kind not in MVP_KINDS:
        return _fail(
            "validation_form",
            MSG_KIND_MVP,
            http_status=400,
            errors={"kind": [MSG_KIND_MVP]},
        )
    try:
        require_scopes(client, parsed["scope"])
    except AuthFailure as exc:
        return _fail(exc.error_code, exc.user_message, http_status=exc.status)

    file_a = file_b = None
    upload = None
    sm_files: list = []
    if kind == contract_service.KIND_MATCH:
        file_a = _slot_file(posted, "file_a")
        file_b = _slot_file(posted, "file_b")
        for field, slot in (("file_a", file_a), ("file_b", file_b)):
            checked = _validate_upload_slot(client, slot, field)
            if not checked.ok:
                return checked
        hash_a = _read_hash(file_a)
        hash_b = _read_hash(file_b)
        content_hash = process_security_service.hash_bytes(f"{hash_a}:{hash_b}".encode())
    elif kind == contract_service.KIND_MERGE:
        sm_files = _list_files(posted, "files")
        if len(sm_files) < 2:
            return _fail(
                "validation_form",
                contract_service.MSG_NEED_FILES,
                http_status=400,
                errors={"files": [contract_service.MSG_NEED_FILES]},
            )
        hashes = []
        for slot in sm_files:
            checked = _validate_upload_slot(client, slot, "files")
            if not checked.ok:
                return checked
            hashes.append(_read_hash(slot))
        content_hash = process_security_service.hash_bytes(":".join(hashes).encode())
    else:
        upload = _first_file(posted)
        security = process_security_service.validate_upload(
            filename=getattr(upload, "name", "") or "",
            size_bytes=getattr(upload, "size", 0) or 0,
            company=client.company,
        )
        if not security.ok:
            return _fail(
                security.error_code or "validation_form",
                security.user_message,
                http_status=400,
                errors=security.errors,
            )
        raw = b""
        if hasattr(upload, "read"):
            raw = upload.read() or b""
            if hasattr(upload, "seek"):
                upload.seek(0)
        content_hash = process_security_service.hash_bytes(raw) if raw else ""
        if kind == contract_service.KIND_SPLIT:
            sm_files = [upload]

    parsed["content_hash"] = content_hash
    request_hash = _request_hash(parsed, content_hash)
    replay = _lookup_idempotency(client, parsed.get("idempotency_key") or "", request_hash)
    if replay is not None:
        return replay

    if kind == contract_service.KIND_PIPELINE:
        return _run_pipeline(client, posted, parsed, upload, content_hash)

    project_result = _resolve_project(client, parsed["project_slug"], kind)
    if not project_result.ok:
        return project_result
    project = project_result.payload["project"]

    actor = _actor(client, project)

    try:
        if kind == contract_service.KIND_MATCH:
            if parsed["wait"] == contract_service.WAIT_ASYNC:
                return _fail(
                    "validation_form",
                    MSG_MATCH_WAIT,
                    http_status=400,
                    errors={"wait": [MSG_MATCH_WAIT]},
                )
            runner = _run_match(actor, project, file_a, file_b, client, parsed)
        elif kind == contract_service.KIND_SCOUT:
            if parsed["wait"] == contract_service.WAIT_ASYNC:
                return _fail(
                    "validation_form",
                    MSG_SCOUT_WAIT,
                    http_status=400,
                    errors={"wait": [MSG_SCOUT_WAIT]},
                )
            runner = _run_scout(actor, project, upload, client, parsed)
        elif kind == contract_service.KIND_CLEAN:
            if parsed["wait"] == contract_service.WAIT_ASYNC:
                return _fail(
                    "validation_form",
                    MSG_CLEAN_WAIT,
                    http_status=400,
                    errors={"wait": [MSG_CLEAN_WAIT]},
                )
            runner = _run_clean(actor, project, upload, client, parsed)
        elif kind in {contract_service.KIND_SPLIT, contract_service.KIND_MERGE}:
            if parsed["wait"] == contract_service.WAIT_ASYNC:
                return _fail(
                    "validation_form",
                    MSG_SM_WAIT,
                    http_status=400,
                    errors={"wait": [MSG_SM_WAIT]},
                )
            runner = _run_sm(kind, actor, project, sm_files, client, parsed)
        elif parsed["wait"] == contract_service.WAIT_ASYNC:
            runner = _queue_job(actor, project, upload, client, parsed)
        else:
            runner = _run_sync(kind, actor, project, upload, client, parsed)
    except Exception:
        logger.exception("api jobs/run failed kind=%s slug=%s", kind, project.slug)
        return _fail("unexpected", MSG_UNEXPECTED, http_status=500)

    if not runner.ok:
        return _map_runner_failure(runner)

    job = runner.payload.get("job")
    if job is None:
        return _fail("unexpected", MSG_UNEXPECTED, http_status=500)

    if kind == contract_service.KIND_GATE and parsed["wait"] == contract_service.WAIT_SYNC:
        verdict = _gate_verdict(job)
        ok = verdict == contract_service.GATE_ACCEPTED and job.status == job.STATUS_COMPLETED
        errors = _gate_errors(job)
        summary = {
            "verdict": verdict,
            "gate_status": (job.input_suggestions or {}).get("gate_result", {}).get("status"),
            "rows_read": job.rows_read,
            "rows_ok": job.rows_ok,
            "rows_rejected": job.rows_rejected,
        }
        message = MSG_DRY_RUN_OK if parsed.get("dry_run") else MSG_GATE_OK
    elif kind == contract_service.KIND_MATCH:
        summary = _match_summary(job)
        ok = (
            getattr(job, "verdict", "") == "passed"
            and job.status in {job.STATUS_COMPLETED, job.STATUS_PARTIAL}
        )
        errors = []
        message = MSG_MATCH_OK
    elif kind == contract_service.KIND_SCOUT:
        summary = _scout_summary(job)
        ok = job.status != job.STATUS_FAILED
        errors = []
        message = MSG_SCOUT_OK
    elif kind == contract_service.KIND_CLEAN:
        summary = _clean_summary(job)
        ok = job.status == job.STATUS_COMPLETED
        errors = []
        if not ok and getattr(job, "error_message", ""):
            errors.append(
                contract_service.error_item(
                    row=None,
                    field="",
                    code=getattr(job, "error_code", "") or "failed",
                    message=job.error_message,
                )
            )
        if ok and parsed.get("dry_run"):
            message = MSG_DRY_RUN_OK
        elif ok:
            message = MSG_CLEAN_OK
        else:
            message = job.error_message or MSG_CLEAN_OK
    elif kind in {contract_service.KIND_SPLIT, contract_service.KIND_MERGE}:
        summary = _sm_summary(job)
        ok = job.status == job.STATUS_COMPLETED
        errors = []
        if not ok and getattr(job, "error_message", ""):
            errors.append(
                contract_service.error_item(
                    row=None,
                    field="",
                    code=getattr(job, "error_code", "") or "failed",
                    message=job.error_message,
                )
            )
        if ok and parsed.get("dry_run"):
            message = MSG_DRY_RUN_OK
        elif ok:
            message = (
                MSG_SPLIT_OK if kind == contract_service.KIND_SPLIT else MSG_MERGE_OK
            )
        else:
            message = job.error_message or (
                MSG_SPLIT_OK if kind == contract_service.KIND_SPLIT else MSG_MERGE_OK
            )
    elif parsed["wait"] == contract_service.WAIT_ASYNC:
        ok = False
        errors = []
        summary = {"queued": True}
        message = MSG_ASYNC_OK
    else:
        ok = job.status in {job.STATUS_COMPLETED, job.STATUS_PARTIAL}
        errors = []
        summary = {
            "rows_read": job.rows_read,
            "rows_ok": job.rows_ok,
            "rows_rejected": job.rows_rejected,
        }
        message = _sync_message(kind, parsed)

    body = _envelope(
        job=job,
        parsed=parsed,
        kind=kind,
        content_hash=content_hash,
        ok=ok,
        summary=summary,
        errors=errors,
    )
    http_status = contract_service.http_status_for(
        wait=parsed["wait"],
        status=_machine_status(job),
    )
    _store_idempotency(
        client,
        parsed,
        request_hash,
        job=job,
        envelope=body,
        user_message=message,
        http_status=http_status,
    )
    from apps.platform_api.services import webhook_service

    webhook_service.notify_from_envelope(client, body)
    return OperationResult.success(message, envelope=body, http_status=http_status)


KIND_TO_PROJECT = KIND_TO_PROJECT
