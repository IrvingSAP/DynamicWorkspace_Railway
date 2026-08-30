from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.company.models import Company
from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import storage_service
from apps.file_clean.models import CleanJob
from apps.file_match.models import FileMatchJob
from apps.file_pipeline.models import PipelineRun
from apps.file_split_merge.models import SplitMergeJob
from apps.platform_api.models import (
    SCOPE_ARTIFACTS_DOWNLOAD,
    SCOPE_JOBS_READ,
    ApiClient,
)
from apps.platform_api.services import contract_service, job_audit_service, process_security_service
from apps.platform_api.services.bearer_auth import AuthFailure, require_scopes
from apps.platform_api.services.job_run_service import (
    KIND_TO_PROJECT,
    _artifacts as _base_artifacts,
    _clean_summary,
    _envelope,
    _gate_errors,
    _gate_verdict,
    _match_summary,
    _scout_job_view,
    _scout_summary,
    _sm_summary,
    serialize_pipeline_run,
)
from apps.structure_scout.models import ScoutDetectionState

MSG_LIST_OK = "Listado de jobs."
MSG_DETAIL_OK = "Job encontrado."
MSG_NO_BYTES = "El artifact no está disponible."
MSG_EXPIRED = process_security_service.MSG_ARTIFACT

KIND_FROM_PROJECT = {
    value: key
    for key, value in KIND_TO_PROJECT.items()
    if key not in {contract_service.KIND_SPLIT, contract_service.KIND_MERGE}
}
LIST_MAX = 100


def _fail(error_code: str, user_message: str, *, http_status: int, errors: dict | None = None):
    return OperationResult.failure(
        error_code,
        user_message,
        errors=errors,
        http_status=http_status,
    )


def _jobs_qs(client: ApiClient):
    return DmsExecutionJob.objects.select_related(
        "project",
        "project__company",
        "version",
        "executed_by",
    ).filter(project__company=client.company)


def get_job_for_client(client: ApiClient, job_id) -> DmsExecutionJob | None:
    return _jobs_qs(client).filter(pk=job_id).first()


def get_pipeline_run_for_client(client: ApiClient, run_id) -> PipelineRun | None:
    return (
        PipelineRun.objects.select_related("pipeline", "version")
        .prefetch_related("steps")
        .filter(pk=run_id, pipeline__company=client.company)
        .first()
    )


def _match_qs(company):
    return FileMatchJob.objects.select_related("project", "published_version").filter(
        project__company=company
    )


def _clean_qs(company):
    return CleanJob.objects.select_related("project", "published_version").filter(
        project__company=company
    )


def _sm_qs(company):
    return SplitMergeJob.objects.select_related("project", "published_version").filter(
        project__company=company
    )


def _scout_qs(company):
    return ScoutDetectionState.objects.select_related("project", "sample").filter(
        project__company=company
    )


def find_work(company, job_id):
    dms = (
        DmsExecutionJob.objects.select_related("project", "project__company", "version")
        .filter(pk=job_id, project__company=company)
        .first()
    )
    if dms is not None:
        return ("dms", dms)
    match = _match_qs(company).filter(pk=job_id).first()
    if match is not None:
        return ("match", match)
    clean = _clean_qs(company).filter(pk=job_id).first()
    if clean is not None:
        return ("clean", clean)
    sm = _sm_qs(company).filter(pk=job_id).first()
    if sm is not None:
        return ("sm", sm)
    scout = _scout_qs(company).filter(pk=job_id).first()
    if scout is not None:
        return ("scout", scout)
    run = (
        PipelineRun.objects.select_related("pipeline", "version")
        .prefetch_related("steps")
        .filter(pk=job_id, pipeline__company=company)
        .first()
    )
    if run is not None:
        return ("pipeline", run)
    return None


def _kind_of(job: DmsExecutionJob) -> str:
    return KIND_FROM_PROJECT.get(job.project.project_kind, job.project.project_kind)


def _is_expired(job, company) -> bool:
    ttl = process_security_service.artifact_ttl_seconds(company)
    stamp = (
        getattr(job, "finished_at", None)
        or getattr(job, "updated_at", None)
        or getattr(job, "created_at", None)
    )
    if stamp is None:
        return False
    return timezone.now() - stamp > timedelta(seconds=ttl)


def _signed_artifacts(job, client: ApiClient) -> dict:
    artifacts = _base_artifacts(job)
    job_id = str(job.id)
    ttl = process_security_service.artifact_ttl_seconds(client.company)
    if artifacts.get("report_url"):
        token = process_security_service.sign_artifact_token(
            company_id=client.company_id,
            job_id=job_id,
            name="report",
        )
        artifacts["report_url"] = f"/api/v1/jobs/{job_id}/report?token={token}"
        artifacts["report_ttl_seconds"] = ttl
    if artifacts.get("output_url"):
        token = process_security_service.sign_artifact_token(
            company_id=client.company_id,
            job_id=job_id,
            name="output",
        )
        artifacts["output_url"] = f"/api/v1/jobs/{job_id}/output?token={token}"
        artifacts["output_ttl_seconds"] = ttl
    return artifacts


def _audit(job) -> dict:
    return job_audit_service.job_audit_payload(job)


def _content_hash(job) -> str:
    direct = getattr(job, "input_content_hash", "") or ""
    if direct:
        return direct
    hash_a = getattr(job, "file_a_hash", "") or ""
    hash_b = getattr(job, "file_b_hash", "") or ""
    if hash_a or hash_b:
        return f"{hash_a}:{hash_b}"
    inputs = getattr(job, "inputs", None) or []
    if isinstance(inputs, list) and inputs:
        return ":".join(str((item or {}).get("content_hash") or "") for item in inputs)
    return ""


def _ops_envelope(job, client: ApiClient, kind: str, summary: dict, ok: bool, *, project_slug: str | None = None):
    slug = project_slug or getattr(getattr(job, "project", None), "slug", None)
    body = _envelope(
        job=job,
        parsed={"wait": contract_service.WAIT_SYNC, "project_slug": slug},
        kind=kind,
        content_hash=_content_hash(job),
        ok=ok,
        summary=summary,
        errors=[],
    )
    body["artifacts"] = _signed_artifacts(job, client)
    body["audit"] = _audit(job)
    return body


def serialize_job(job: DmsExecutionJob, client: ApiClient) -> dict:
    kind = _kind_of(job)
    if kind == contract_service.KIND_GATE:
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
    else:
        ok = job.status in {job.STATUS_COMPLETED, job.STATUS_PARTIAL}
        errors = []
        summary = {
            "rows_read": job.rows_read,
            "rows_ok": job.rows_ok,
            "rows_rejected": job.rows_rejected,
        }
    body = _envelope(
        job=job,
        parsed={"wait": contract_service.WAIT_SYNC, "project_slug": job.project.slug},
        kind=kind,
        content_hash=job.input_content_hash or "",
        ok=ok,
        summary=summary,
        errors=errors,
    )
    body["artifacts"] = _signed_artifacts(job, client)
    body["audit"] = _audit(job)
    return body


def serialize_match(job: FileMatchJob, client: ApiClient) -> dict:
    ok = job.verdict == job.VERDICT_PASSED and job.status in {
        job.STATUS_COMPLETED,
        job.STATUS_PARTIAL,
    }
    return _ops_envelope(job, client, contract_service.KIND_MATCH, _match_summary(job), ok)


def serialize_clean(job: CleanJob, client: ApiClient) -> dict:
    ok = job.status == job.STATUS_COMPLETED
    return _ops_envelope(job, client, contract_service.KIND_CLEAN, _clean_summary(job), ok)


def serialize_sm(job: SplitMergeJob, client: ApiClient) -> dict:
    kind = (
        contract_service.KIND_SPLIT
        if job.operation == job.OPERATION_SPLIT
        else contract_service.KIND_MERGE
    )
    ok = job.status == job.STATUS_COMPLETED
    return _ops_envelope(job, client, kind, _sm_summary(job), ok)


def serialize_scout(state: ScoutDetectionState, client: ApiClient) -> dict:
    job = _scout_job_view(state)
    ok = job.status != job.STATUS_FAILED
    body = _ops_envelope(
        job,
        client,
        contract_service.KIND_SCOUT,
        _scout_summary(job),
        ok,
        project_slug=state.project.slug,
    )
    body["audit"] = _audit(state)
    return body


def serialize_work(tag: str, obj, client: ApiClient) -> dict:
    if tag == "dms":
        return serialize_job(obj, client)
    if tag == "match":
        return serialize_match(obj, client)
    if tag == "clean":
        return serialize_clean(obj, client)
    if tag == "sm":
        return serialize_sm(obj, client)
    if tag == "scout":
        return serialize_scout(obj, client)
    return serialize_pipeline_run(obj)


def get_job(client: ApiClient, job_id) -> OperationResult:
    try:
        require_scopes(client, SCOPE_JOBS_READ)
    except AuthFailure as exc:
        return _fail(exc.error_code, exc.user_message, http_status=exc.status)
    found = find_work(client.company, job_id)
    if found is None:
        return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
    tag, obj = found
    return OperationResult.success(
        MSG_DETAIL_OK, envelope=serialize_work(tag, obj, client), http_status=200
    )


def _page_args(query):
    try:
        limit = min(LIST_MAX, max(1, int(query.get("limit") or 20)))
    except (TypeError, ValueError):
        limit = 20
    try:
        offset = max(0, int(query.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    return limit, offset


def _apply_common_filters(qs, query, *, api_lookup: str | None, apply_status: bool = True):
    status = (query.get("status") or "").strip()
    if apply_status and status:
        qs = qs.filter(status=status)
    client_id = (query.get("api_client_id") or "").strip()
    if client_id and api_lookup:
        qs = qs.filter(**{api_lookup: client_id})
    created_from = parse_datetime((query.get("created_from") or "").strip())
    created_to = parse_datetime((query.get("created_to") or "").strip())
    if created_from:
        qs = qs.filter(created_at__gte=created_from)
    if created_to:
        qs = qs.filter(created_at__lte=created_to)
    return qs


def _window_rows(qs, serialize_fn, window: int):
    total = qs.count()
    rows = [(obj.created_at, serialize_fn(obj)) for obj in qs.order_by("-created_at")[:window]]
    return rows, total


def list_jobs(client: ApiClient, query) -> OperationResult:
    try:
        require_scopes(client, SCOPE_JOBS_READ)
    except AuthFailure as exc:
        return _fail(exc.error_code, exc.user_message, http_status=exc.status)
    kind = (query.get("kind") or "").strip()
    limit, offset = _page_args(query)
    window = offset + limit
    company = client.company
    batches: list[tuple[list, int]] = []

    def take_dms():
        qs = _jobs_qs(client)
        if kind:
            project_kind = KIND_TO_PROJECT.get(kind)
            if project_kind:
                qs = qs.filter(project__project_kind=project_kind)
        qs = _apply_common_filters(qs, query, api_lookup="input_suggestions__api_client_id")
        return _window_rows(qs, lambda job: serialize_job(job, client), window)

    def take_match():
        qs = _apply_common_filters(
            _match_qs(company), query, api_lookup="metrics__api__api_client_id"
        )
        return _window_rows(qs, lambda job: serialize_match(job, client), window)

    def take_clean():
        qs = _apply_common_filters(
            _clean_qs(company), query, api_lookup="metrics__api__api_client_id"
        )
        return _window_rows(qs, lambda job: serialize_clean(job, client), window)

    def take_sm(operation: str | None):
        qs = _sm_qs(company)
        if operation:
            qs = qs.filter(operation=operation)
        qs = _apply_common_filters(qs, query, api_lookup="metrics__api__api_client_id")
        return _window_rows(qs, lambda job: serialize_sm(job, client), window)

    def take_scout():
        qs = _scout_qs(company)
        status = (query.get("status") or "").strip()
        if status == contract_service.STATUS_FAILED:
            qs = qs.filter(status=ScoutDetectionState.STATUS_FAILED)
        elif status == contract_service.STATUS_COMPLETED:
            qs = qs.exclude(status=ScoutDetectionState.STATUS_FAILED)
        elif status:
            qs = qs.none()
        qs = _apply_common_filters(
            qs,
            query,
            api_lookup="suggestions_snapshot__api__api_client_id",
            apply_status=False,
        )
        return _window_rows(qs, lambda state: serialize_scout(state, client), window)

    def take_pipeline():
        qs = PipelineRun.objects.select_related("pipeline", "version").filter(
            pipeline__company=company
        )
        qs = _apply_common_filters(qs, query, api_lookup="api_client_id")
        return _window_rows(qs, serialize_pipeline_run, window)

    if kind == contract_service.KIND_PIPELINE:
        batches.append(take_pipeline())
    elif kind == contract_service.KIND_MATCH:
        batches.append(take_match())
    elif kind == contract_service.KIND_CLEAN:
        batches.append(take_clean())
    elif kind == contract_service.KIND_SPLIT:
        batches.append(take_sm(SplitMergeJob.OPERATION_SPLIT))
    elif kind == contract_service.KIND_MERGE:
        batches.append(take_sm(SplitMergeJob.OPERATION_MERGE))
    elif kind == contract_service.KIND_SCOUT:
        batches.append(take_scout())
    elif kind:
        if KIND_TO_PROJECT.get(kind):
            batches.append(take_dms())
        else:
            batches.append(([], 0))
    else:
        batches.extend(
            [
                take_dms(),
                take_match(),
                take_clean(),
                take_sm(None),
                take_scout(),
                take_pipeline(),
            ]
        )

    merged = []
    total = 0
    for rows, count in batches:
        merged.extend(rows)
        total += count
    merged.sort(key=lambda item: item[0], reverse=True)
    page = [item[1] for item in merged[offset : offset + limit]]
    return OperationResult.success(
        MSG_LIST_OK,
        jobs=page,
        total=total,
        limit=limit,
        offset=offset,
        http_status=200,
    )


def _stored_for(job, name: str) -> str:
    if name == "report":
        return (
            getattr(job, "report_path", "")
            or getattr(job, "change_log_path", "")
            or getattr(job, "manifest_path", "")
            or ""
        )
    output = getattr(job, "output_stored_path", "") or ""
    if not output:
        outputs = getattr(job, "outputs", None) or []
        if isinstance(outputs, list) and len(outputs) == 1:
            output = (outputs[0] or {}).get("stored_path") or ""
    return output


def _filename_for(job, name: str, stored: str) -> str:
    if name == "report":
        return Path(stored).name or "report.json"
    filename = getattr(job, "output_filename", "") or ""
    if not filename:
        outputs = getattr(job, "outputs", None) or []
        if isinstance(outputs, list) and len(outputs) == 1:
            filename = (outputs[0] or {}).get("filename") or ""
    return filename or Path(stored).name or "output.bin"


def open_artifact(client: ApiClient | None, request, job_id, name: str) -> OperationResult:
    token = (request.GET.get("token") or "").strip()
    job = None
    company = None
    if token:
        try:
            company_id, token_job, token_name = process_security_service.read_artifact_token(
                token, max_age=7 * 24 * 3600
            )
        except AuthFailure as exc:
            return _fail(exc.error_code, exc.user_message, http_status=exc.status)
        if str(token_job) != str(job_id) or token_name != name:
            return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
        company = Company.objects.filter(pk=company_id).first()
        if company is None:
            return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
        found = find_work(company, job_id)
        if found is None:
            return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
        job = found[1]
        try:
            process_security_service.read_artifact_token(
                token, max_age=process_security_service.artifact_ttl_seconds(company)
            )
        except AuthFailure as exc:
            return _fail(exc.error_code, exc.user_message, http_status=exc.status)
    elif client is not None:
        try:
            require_scopes(client, SCOPE_ARTIFACTS_DOWNLOAD)
        except AuthFailure as exc:
            return _fail(exc.error_code, exc.user_message, http_status=exc.status)
        found = find_work(client.company, job_id)
        if found is None:
            return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
        job = found[1]
        company = client.company
    else:
        return _fail("invalid_token", "Credencial ausente o inválida.", http_status=401)
    if job is None:
        return _fail("not_found", process_security_service.MSG_NOT_FOUND, http_status=404)
    if _is_expired(job, company):
        return _fail("not_found", MSG_EXPIRED, http_status=404)
    stored = _stored_for(job, name)
    if not stored:
        return _fail("not_found", MSG_NO_BYTES, http_status=404)
    filename = _filename_for(job, name, stored)
    path = storage_service.absolute_from_stored(stored)
    if not path.is_file():
        return _fail("not_found", MSG_NO_BYTES, http_status=404)
    return OperationResult.success(
        "",
        path=str(path),
        filename=filename,
        http_status=200,
    )
