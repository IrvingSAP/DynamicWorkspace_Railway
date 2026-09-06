from __future__ import annotations

from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.models import DmsExecutionJob
from apps.platform_api.models import SCOPE_JOBS_CANCEL, ApiClient
from apps.platform_api.services import contract_service, process_security_service
from apps.platform_api.services.bearer_auth import AuthFailure, require_scopes
from apps.file_pipeline.models import PipelineRun
from apps.platform_api.services.job_query_service import (
    find_work,
    serialize_job,
)
from apps.platform_api.services.job_run_service import serialize_pipeline_run

MSG_CANCELLED = "Job cancelado."
MSG_CANCEL_DONE = "Este job ya no se puede cancelar."
MSG_UNEXPECTED = "Ocurrió un error al cancelar. Si persiste, contacte al administrador."

TERMINAL = {
    DmsExecutionJob.STATUS_COMPLETED,
    DmsExecutionJob.STATUS_PARTIAL,
    DmsExecutionJob.STATUS_FAILED,
    DmsExecutionJob.STATUS_CANCELLED,
}


def _fail(error_code: str, user_message: str, *, http_status: int, errors: dict | None = None):
    return OperationResult.failure(
        error_code,
        user_message,
        errors=errors,
        http_status=http_status,
    )


def cancel_job(client: ApiClient, job_id) -> OperationResult:
    try:
        require_scopes(client, SCOPE_JOBS_CANCEL)
    except AuthFailure as exc:
        return _fail(exc.error_code, exc.user_message, http_status=exc.status)
    found = find_work(client.company, job_id)
    if found is None:
        return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
    tag, obj = found
    if tag == "pipeline":
        run = obj
        if run.status in {
            PipelineRun.STATUS_COMPLETED,
            PipelineRun.STATUS_FAILED,
            PipelineRun.STATUS_CANCELLED,
        }:
            return _fail(
                "cancel_not_allowed",
                MSG_CANCEL_DONE,
                http_status=409,
                errors={"status": [MSG_CANCEL_DONE]},
            )
        run.status = PipelineRun.STATUS_CANCELLED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        body = serialize_pipeline_run(run)
        from apps.platform_api.services import webhook_service

        webhook_service.notify_from_envelope(client, body)
        return OperationResult.success(MSG_CANCELLED, envelope=body, http_status=200)
    if tag != "dms":
        return _fail(
            "cancel_not_allowed",
            MSG_CANCEL_DONE,
            http_status=409,
            errors={"status": [MSG_CANCEL_DONE]},
        )
    job = obj
    if job.status in TERMINAL:
        return _fail(
            "cancel_not_allowed",
            MSG_CANCEL_DONE,
            http_status=409,
            errors={"status": [MSG_CANCEL_DONE]},
        )
    suggestions = dict(job.input_suggestions or {})
    suggestions["cancelled_by_api_client_id"] = str(client.pk)
    job.status = DmsExecutionJob.STATUS_CANCELLED
    job.input_suggestions = suggestions
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "input_suggestions", "finished_at", "updated_at"])
    body = serialize_job(job, client)
    from apps.platform_api.services import webhook_service

    webhook_service.notify_from_envelope(client, body)
    return OperationResult.success(MSG_CANCELLED, envelope=body, http_status=200)
