from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.platform_api.services.bearer_auth import (
    AuthFailure,
    authenticate_token,
    parse_bearer,
    require_scopes,
)
from apps.platform_api.services import (
    contract_service,
    integration_service,
    job_ops_service,
    job_query_service,
    job_run_service,
    openapi_service,
    process_security_service,
)


def _error(exc: AuthFailure) -> JsonResponse:
    return JsonResponse(
        {
            "ok": False,
            "error_code": exc.error_code,
            "user_message": exc.user_message,
        },
        status=exc.status,
    )


def _client_or_error(request):
    raw = parse_bearer(request.headers.get("Authorization"))
    if not raw:
        return None, _error(
            AuthFailure(401, "invalid_token", "Credencial ausente o inválida."),
        )
    try:
        client = authenticate_token(raw)
        process_security_service.enforce_rate_limit(client)
    except AuthFailure as exc:
        return None, _error(exc)
    return client, None


def _form_error(result) -> JsonResponse:
    status = result.payload.get("http_status") or contract_service.http_status_for(
        wait=contract_service.WAIT_SYNC,
        status=contract_service.STATUS_FAILED,
        protocol_error=result.error_code,
    )
    items = []
    for field, messages in (result.errors or {}).items():
        for message in messages:
            items.append(
                contract_service.error_item(row=None, field=field, code=result.error_code or "", message=message)
            )
    return JsonResponse(
        {
            "ok": False,
            "error_code": result.error_code,
            "user_message": result.user_message,
            "errors": items,
        },
        status=status,
    )


@csrf_exempt
@require_GET
def whoami(request):
    client, err = _client_or_error(request)
    if err:
        return err
    policy = process_security_service.get_policy(client.company)
    return JsonResponse(
        {
            "ok": True,
            "client_code": client.code,
            "environment": client.environment,
            "company": client.company.name_short,
            "scopes": client.scopes,
            "process_policy": {
                "max_upload_bytes": policy.max_upload_bytes,
                "rate_per_minute": policy.rate_per_minute,
                "artifact_ttl_hours": policy.artifact_ttl_hours,
                "require_published": True,
            },
        }
    )


@csrf_exempt
@require_GET
def contract_catalog(request):
    client, err = _client_or_error(request)
    if err:
        return err
    body = contract_service.catalog()
    body["ok"] = True
    body["client_code"] = client.code
    return JsonResponse(body)


@csrf_exempt
@require_GET
def openapi_catalog(request):
    client, err = _client_or_error(request)
    if err:
        return err
    body = openapi_service.catalog()
    body["ok"] = True
    body["user_message"] = openapi_service.MSG_CATALOG
    body["client_code"] = client.code
    return JsonResponse(body)


@csrf_exempt
@require_GET
def integration_catalog(request):
    client, err = _client_or_error(request)
    if err:
        return err
    body = integration_service.catalog()
    body["ok"] = True
    body["user_message"] = integration_service.MSG_CATALOG
    body["client_code"] = client.code
    return JsonResponse(body)


@csrf_exempt
@require_http_methods(["POST"])
def jobs_validate(request):
    client, err = _client_or_error(request)
    if err:
        return err
    posted = contract_service.posted_from_request(request)
    files_map = posted.get("_files") or {}
    has_files = any(files_map.values())
    result = contract_service.validate_posted(posted, require_files=has_files)
    if not result.ok:
        return _form_error(result)
    parsed = result.payload["parsed"]
    try:
        require_scopes(client, parsed["scope"])
    except AuthFailure as exc:
        return _error(exc)
    return JsonResponse(
        {
            "ok": True,
            "user_message": result.user_message,
            "validated": True,
            "executed": False,
            "request": parsed,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def jobs_run(request):
    client, err = _client_or_error(request)
    if err:
        return err
    posted = contract_service.posted_from_request(request)
    result = job_run_service.run_job(client, posted)
    if not result.ok:
        return _form_error(result)
    body = dict(result.payload.get("envelope") or {})
    body["user_message"] = result.user_message
    return JsonResponse(body, status=int(result.payload.get("http_status") or 200))


def _optional_client(request):
    raw = parse_bearer(request.headers.get("Authorization"))
    if not raw:
        return None, None
    try:
        client = authenticate_token(raw)
        process_security_service.enforce_rate_limit(client)
    except AuthFailure as exc:
        return None, _error(exc)
    return client, None


@csrf_exempt
@require_GET
def jobs_list(request):
    client, err = _client_or_error(request)
    if err:
        return err
    result = job_query_service.list_jobs(client, request.GET)
    if not result.ok:
        return _form_error(result)
    return JsonResponse(
        {
            "ok": True,
            "user_message": result.user_message,
            "jobs": result.payload.get("jobs") or [],
            "total": result.payload.get("total") or 0,
            "limit": result.payload.get("limit"),
            "offset": result.payload.get("offset"),
        }
    )


@csrf_exempt
@require_GET
def jobs_detail(request, job_id):
    client, err = _client_or_error(request)
    if err:
        return err
    result = job_query_service.get_job(client, job_id)
    if not result.ok:
        return _form_error(result)
    body = dict(result.payload.get("envelope") or {})
    body["user_message"] = result.user_message
    return JsonResponse(body)


def _jobs_artifact(request, job_id, name: str):
    client, err = _optional_client(request)
    if err:
        return err
    result = job_query_service.open_artifact(client, request, job_id, name)
    if not result.ok:
        return _form_error(result)
    path = result.payload["path"]
    filename = result.payload["filename"]
    handle = open(path, "rb")
    return FileResponse(handle, as_attachment=True, filename=filename)


@csrf_exempt
@require_GET
def jobs_report(request, job_id):
    return _jobs_artifact(request, job_id, "report")


@csrf_exempt
@require_GET
def jobs_output(request, job_id):
    return _jobs_artifact(request, job_id, "output")


@csrf_exempt
@require_http_methods(["POST"])
def jobs_cancel(request, job_id):
    client, err = _client_or_error(request)
    if err:
        return err
    result = job_ops_service.cancel_job(client, job_id)
    if not result.ok:
        return _form_error(result)
    body = dict(result.payload.get("envelope") or {})
    body["user_message"] = result.user_message
    return JsonResponse(body, status=int(result.payload.get("http_status") or 200))


@csrf_exempt
@require_http_methods(["POST"])
def pipeline_runs(request, pipeline_id: str):
    client, err = _client_or_error(request)
    if err:
        return err
    posted = contract_service.posted_from_request(request)
    posted["kind"] = contract_service.KIND_PIPELINE
    posted["pipeline_id"] = pipeline_id
    result = job_run_service.run_job(client, posted)
    if not result.ok:
        return _form_error(result)
    body = dict(result.payload.get("envelope") or {})
    body["user_message"] = result.user_message
    return JsonResponse(body, status=int(result.payload.get("http_status") or 200))
