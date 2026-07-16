from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.file_intake.services import (
    file_intake_persistence_service,
    file_intake_service,
)
from apps.dms.mapping.services import mapping_project_service
from apps.projects.services import project_service


def _intake_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    editor = file_intake_service.get_hub_context(project, membership)
    editor["can_upload_sample"] = file_intake_persistence_service.user_can_upload_sample(
        request.user, project
    )
    editor["can_upload_production"] = (
        file_intake_persistence_service.user_can_upload_production(request.user, project)
    )
    return {
        "project": project,
        "membership": membership,
        "app_nav_active": "filepipe_mapping",
        "filepipe_nav_open": True,
        "sample_upload_url": reverse(
            "dms:file_intake_sample_upload", kwargs={"project_slug": project.slug}
        ),
        "production_upload_url": reverse(
            "dms:file_intake_production_upload", kwargs={"project_slug": project.slug}
        ),
        **editor,
    }


@_intake_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    return render(request, "dms/file_intake/hub.html", _base_context(request, project))


@_intake_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    return render(
        request, "dms/file_intake/hub_help.html", _base_context(request, project)
    )


@_intake_view
@require_http_methods(["POST"])
def sample_upload(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
            status=403,
        )
    result = file_intake_persistence_service.upload_sample(
        request.user, project, request.FILES.get("file")
    )
    return _json_result(result)


@_intake_view
@require_http_methods(["GET"])
def sample_preview(request, project_slug: str, sample_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
            status=403,
        )
    result = file_intake_persistence_service.get_sample_preview(
        request.user, project, sample_id
    )
    if not result.ok:
        return JsonResponse(
            {"ok": False, "message": result.user_message, "errors": result.errors or {}},
            status=404 if result.error_code == "not_found" else 400,
        )
    sample = result.payload["sample"]
    return JsonResponse(
        {
            "ok": True,
            "stored_file_id": str(sample.id),
            "original_filename": sample.original_filename,
            "size_bytes": sample.size_bytes,
            "suggestions": result.payload.get("suggestions") or {},
            "preview_rows": result.payload.get("preview_rows") or [],
        }
    )


@_intake_view
@require_http_methods(["POST"])
def sample_delete(request, project_slug: str, sample_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
            status=403,
        )
    result = file_intake_persistence_service.delete_sample(
        request.user, project, sample_id
    )
    return _json_result(result, success_status=200)


@_intake_view
@require_http_methods(["POST"])
def production_upload(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
            status=403,
        )
    result = file_intake_persistence_service.upload_production(
        request.user, project, request.FILES.get("file")
    )
    return _json_result(result)


def _json_result(result, *, success_status=200):
    if result.ok:
        payload = result.payload or {}
        body = {
            "ok": True,
            "message": result.user_message,
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
        return JsonResponse(body, status=success_status)

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
