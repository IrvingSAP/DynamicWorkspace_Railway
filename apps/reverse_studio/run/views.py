from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.file_intake.services import file_intake_persistence_service, storage_service
from apps.dms.transform_execution.services import download_token_service, execution_service
from apps.projects.services import project_service
from apps.reverse_studio.projects.services import reverse_project_service
from apps.reverse_studio.run.services import generate_run_service


def _rs_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = reverse_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto Reverse Studio.")
        return None
    return project


def _sidebar() -> dict:
    return {
        "app_nav_active": "reverse_studio",
        "reverse_studio_nav_open": True,
    }


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    hub = generate_run_service.get_hub_context(request.user, project, membership)
    return {
        "project": project,
        "membership": membership,
        **hub,
        **_sidebar(),
    }


@_rs_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(request, "reverse_studio/run/hub.html", _base_context(request, project))


@_rs_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request, "reverse_studio/run/hub_help.html", _base_context(request, project)
    )


@_rs_view
def recent(request, project_slug: str):
    """Alias M5 → M6 (HIS12): un solo historial rico."""
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return redirect("reverse_studio:history_hub", project_slug=project_slug)


@_rs_view
@require_http_methods(["POST"])
def production_upload(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
            status=403,
        )
    result = file_intake_persistence_service.upload_production(
        request.user, project, request.FILES.get("file")
    )
    return _json_intake(result)


@_rs_view
@require_http_methods(["POST"])
def job_preview(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
            status=403,
        )
    result = execution_service.dry_run_job(request.user, project, job_id)
    return _json_execution(result, remap=True)


@_rs_view
@require_http_methods(["POST"])
def job_generate(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
            status=403,
        )
    result = execution_service.run_full_job(
        request.user,
        project,
        job_id,
        download_url_namespace="reverse_studio",
        download_url_names=generate_run_service.DOWNLOAD_URL_NAMES,
    )
    return _json_execution(result, remap=True)


def _download(request, project_slug: str, job_id, kind: str):
    project = reverse_project_service.get_project_for_user(request.user, project_slug)
    if project is None or not generate_run_service.user_can_download(request.user, project):
        raise Http404()
    job = execution_service.get_job(project, job_id)
    if job is None:
        raise Http404()
    expires = request.GET.get("expires", "")
    sig = request.GET.get("sig", "")
    if not download_token_service.verify_download_token(str(job.id), kind, expires, sig):
        return JsonResponse(
            {"ok": False, "message": "Enlace de descarga inválido o expirado."},
            status=403,
        )
    if execution_service.is_download_expired(job):
        return JsonResponse(
            {"ok": False, "message": "Archivo expirado."},
            status=410,
        )
    stored, filename = execution_service.resolve_download_path(job, kind)
    if not stored:
        raise Http404()
    path = storage_service.absolute_from_stored(stored)
    if not path.is_file():
        return JsonResponse(
            {"ok": False, "message": "Archivo expirado."},
            status=410,
        )
    content_type = "application/octet-stream"
    if filename.endswith(".json"):
        content_type = "application/json"
    elif filename.endswith(".html"):
        content_type = "text/html; charset=utf-8"
    elif filename.endswith(".csv"):
        content_type = "text/csv; charset=utf-8"
    elif filename.endswith(".txt"):
        content_type = "text/plain; charset=utf-8"
    response = FileResponse(path.open("rb"), as_attachment=True, filename=filename)
    response["Content-Type"] = content_type
    return response


@_rs_view
@require_http_methods(["GET"])
def download_output(request, project_slug: str, job_id):
    return _download(request, project_slug, job_id, "output")


@_rs_view
@require_http_methods(["GET"])
def download_report(request, project_slug: str, job_id):
    return _download(request, project_slug, job_id, "report")


@_rs_view
@require_http_methods(["GET"])
def download_errors(request, project_slug: str, job_id):
    return _download(request, project_slug, job_id, "errors")


def _json_intake(result):
    if result.ok:
        payload = result.payload or {}
        body = {
            "ok": True,
            "message": generate_run_service.remapped_upload_message(result.user_message),
        }
        for key in (
            "stored_file_id",
            "job_id",
            "original_filename",
            "size_bytes",
            "size_label",
            "suggestions",
            "preview_rows",
            "published_version_number",
        ):
            if key in payload:
                body[key] = payload[key]
        return JsonResponse(body)

    status = 403 if result.error_code == "forbidden" else 400
    if result.error_code == "not_found":
        status = 404
    return JsonResponse(
        {
            "ok": False,
            "message": result.user_message,
            "errors": result.errors or {},
        },
        status=status,
    )


def _json_execution(result, *, remap: bool = False):
    message = result.user_message
    if remap:
        message = generate_run_service.remapped_execute_message(message)

    if result.ok:
        payload = result.payload or {}
        body = {"ok": True, "message": message}
        for key, value in payload.items():
            if key == "job":
                continue
            body[key] = value
        return JsonResponse(body)

    status = 403 if result.error_code == "forbidden" else 400
    if result.error_code == "not_found":
        status = 404
    if result.error_code in {
        "config_invalid",
        "gate_not_published",
        "no_hash",
        "no_matching_job",
        "status_not_accepted",
        "stale",
    }:
        status = 409
    body = {
        "ok": False,
        "message": message,
        "errors": result.errors or {},
        "error_code": result.error_code,
    }
    payload = result.payload or {}
    if payload.get("links"):
        body["links"] = payload["links"]
    if payload.get("gate_project_slug"):
        body["gate_project_slug"] = payload["gate_project_slug"]
    if payload.get("gate_status"):
        body["gate_status"] = payload["gate_status"]
    return JsonResponse(body, status=status)
