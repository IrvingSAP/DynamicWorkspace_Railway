from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.projects.services import match_project_service
from apps.file_match.publish.services import publish_service
from apps.projects.services import project_service


def _publish_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = match_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE MATCH.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    hub = publish_service.get_hub_context(request.user, project, membership)
    return {
        "project": project,
        "membership": membership,
        "publish_hub": hub,
        "can_edit_definition": source_persistence_service.user_can_edit_source(
            request.user, project
        ),
        "publish_url": reverse(
            "file_match:publish_action", kwargs={"project_slug": project.slug}
        ),
        "app_nav_active": "file_match",
        "file_match_nav_open": True,
    }


@_publish_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/publish/hub.html",
        _base_context(request, project),
    )


@_publish_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/publish/hub_help.html",
        _base_context(request, project),
    )


@_publish_view
@require_http_methods(["POST"])
def publish_action(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto FILE MATCH."},
                status=403,
            )
        return redirect("file_match:project_list")

    result = publish_service.publish_match_definition(request.user, project)
    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse(
            "file_match:publish_hub", kwargs={"project_slug": project_slug}
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            payload = result.payload or {}
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "published_version_number": payload.get("published_version_number"),
                    "new_draft_version_number": payload.get("new_draft_version_number"),
                    "warnings": payload.get("warning_messages") or [],
                }
            )
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
                "warnings": source_persistence_service.flatten_validation_messages(
                    (result.payload or {}).get("warnings")
                ),
            },
            status=400,
        )

    if result.ok:
        messages.success(request, result.user_message)
        for warning in (result.payload or {}).get("warning_messages") or []:
            messages.warning(request, warning)
    else:
        messages.error(request, result.user_message)
    return redirect(redirect_to)
