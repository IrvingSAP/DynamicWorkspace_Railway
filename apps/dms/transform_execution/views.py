from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.file_intake.services import storage_service
from apps.dms.mapping.services import mapping_project_service
from apps.dms.transform_execution.services import (
    download_token_service,
    execution_service,
    execution_ui_service,
)
from apps.projects.services import project_service


def _exec_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    ctx = execution_ui_service.get_hub_context(project, membership)
    return {
        "project": project,
        "membership": membership,
        "app_nav_active": "filepipe_mapping",
        "filepipe_nav_open": True,
        "can_execute": execution_service.user_can_execute(request.user, project),
        "file_intake_url": reverse(
            "dms:file_intake_hub", kwargs={"project_slug": project.slug}
        ),
        "preview_url_template": reverse(
            "dms:transform_execution_preview",
            kwargs={"project_slug": project.slug, "job_id": "00000000-0000-0000-0000-000000000000"},
        ),
        "run_url_template": reverse(
            "dms:transform_execution_run",
            kwargs={"project_slug": project.slug, "job_id": "00000000-0000-0000-0000-000000000000"},
        ),
        **ctx,
    }


@_exec_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    return render(request, "dms/transform_execution/hub.html", _base_context(request, project))


@_exec_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    return render(
        request, "dms/transform_execution/hub_help.html", _base_context(request, project)
    )


@_exec_view
def history(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    if not execution_service.user_can_view_history(request.user, project):
        messages.error(request, "No tiene acceso al historial de este proyecto.")
        return redirect("dms:mapping_hub", project_slug=project_slug)
    return render(
        request, "dms/transform_execution/history.html", _base_context(request, project)
    )


@_exec_view
def history_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    if not execution_service.user_can_view_history(request.user, project):
        messages.error(request, "No tiene acceso al historial de este proyecto.")
        return redirect("dms:mapping_hub", project_slug=project_slug)
    return render(
        request,
        "dms/transform_execution/history_help.html",
        _base_context(request, project),
    )


@_exec_view
@require_http_methods(["POST"])
def job_preview(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse({"ok": False, "message": "No tiene acceso a este proyecto DMS."}, status=403)
    result = execution_service.dry_run_job(request.user, project, job_id)
    return _json_result(result)


@_exec_view
@require_http_methods(["POST"])
def job_run(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse({"ok": False, "message": "No tiene acceso a este proyecto DMS."}, status=403)
    result = execution_service.run_full_job(request.user, project, job_id)
    return _json_result(result)


def _download(request, project_slug: str, job_id, kind: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None or not execution_service.user_can_view_history(request.user, project):
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


@_exec_view
@require_http_methods(["GET"])
def download_output(request, project_slug: str, job_id):
    return _download(request, project_slug, job_id, "output")


@_exec_view
@require_http_methods(["GET"])
def download_report(request, project_slug: str, job_id):
    return _download(request, project_slug, job_id, "report")


@_exec_view
@require_http_methods(["GET"])
def download_errors(request, project_slug: str, job_id):
    return _download(request, project_slug, job_id, "errors")


def _json_result(result):
    if result.ok:
        payload = result.payload or {}
        body = {"ok": True, "message": result.user_message}
        for key, value in payload.items():
            if key == "job":
                continue
            body[key] = value
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
