from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.source_profile.services import source_persistence_service
from apps.projects.services import project_service
from apps.reverse_studio.projects.services import reverse_project_service
from apps.reverse_studio.publish.services import publish_service


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
    hub = publish_service.get_hub_context(request.user, project, membership)
    return {
        "project": project,
        "membership": membership,
        "publish_hub": hub,
        "can_edit_definition": source_persistence_service.user_can_edit_source(
            request.user, project
        ),
        "publish_url": reverse(
            "reverse_studio:publish_action", kwargs={"project_slug": project.slug}
        ),
        **_sidebar(),
    }


@_rs_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/publish/hub.html",
        _base_context(request, project),
    )


@_rs_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/publish/hub_help.html",
        _base_context(request, project),
    )


@_rs_view
@require_http_methods(["POST"])
def publish_action(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
                status=403,
            )
        return redirect("reverse_studio:project_list")

    result = publish_service.publish_definition(request.user, project)
    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse(
            "reverse_studio:publish_hub", kwargs={"project_slug": project_slug}
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
