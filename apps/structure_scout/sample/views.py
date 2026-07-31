from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.projects.services import project_service
from apps.structure_scout.projects.services import scout_project_service
from apps.structure_scout.sample.services import sample_upload_service

MSG_NO_ACCESS = "No tiene acceso a este proyecto Explorador."


def _ss_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _sidebar() -> dict:
    return {
        "app_nav_active": "structure_scout",
        "structure_scout_nav_open": True,
    }


def _get_project_or_none(request, project_slug: str):
    return scout_project_service.get_project_for_user(request.user, project_slug)


def _json_result(result, *, success_status=200):
    if result.ok:
        payload = result.payload or {}
        body = {"ok": True, "message": result.user_message}
        for key in (
            "stored_file_id",
            "original_filename",
            "size_bytes",
            "size_label",
            "suggestions",
            "preview_rows",
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


@_ss_view
def sample_hub(request, project_slug: str):
    project = _get_project_or_none(request, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    sample_ctx = sample_upload_service.get_hub_context(request.user, project)
    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    sample_upload_url = reverse(
        "structure_scout:sample_upload", kwargs={"project_slug": project.slug}
    )

    ctx = _sidebar()
    ctx.update(sample_ctx)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
            "sample_upload_url": sample_upload_url,
        }
    )
    return render(request, "structure_scout/sample/hub.html", ctx)


@_ss_view
def sample_hub_help(request, project_slug: str):
    project = _get_project_or_none(request, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")
    ctx = _sidebar()
    ctx.update({"project": project, "company": project.company})
    return render(request, "structure_scout/sample/hub_help.html", ctx)


@_ss_view
@require_http_methods(["POST"])
def sample_upload(request, project_slug: str):
    project = _get_project_or_none(request, project_slug)
    if project is None:
        return JsonResponse({"ok": False, "message": MSG_NO_ACCESS}, status=403)
    result = sample_upload_service.upload_sample(
        request.user, project, request.FILES.get("file")
    )
    return _json_result(result)


@_ss_view
@require_http_methods(["GET"])
def sample_preview(request, project_slug: str, sample_id):
    project = _get_project_or_none(request, project_slug)
    if project is None:
        return JsonResponse({"ok": False, "message": MSG_NO_ACCESS}, status=403)
    result = sample_upload_service.get_sample_preview(
        request.user, project, sample_id
    )
    if not result.ok:
        status = 404 if result.error_code == "not_found" else 403
        if result.error_code not in ("not_found", "forbidden"):
            status = 400
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
            },
            status=status,
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


@_ss_view
@require_http_methods(["POST"])
def sample_delete(request, project_slug: str, sample_id):
    project = _get_project_or_none(request, project_slug)
    if project is None:
        return JsonResponse({"ok": False, "message": MSG_NO_ACCESS}, status=403)
    result = sample_upload_service.delete_sample(request.user, project, sample_id)
    return _json_result(result)
