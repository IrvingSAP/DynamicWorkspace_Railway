from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_match.bridge.services import match_bridge_service
from apps.file_match.projects.services import match_project_service
from apps.projects.services import project_service


def _bridge_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = match_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE MATCH.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    return {
        "project": project,
        "membership": membership,
        "company": project.company,
        "app_nav_active": "file_match",
        "file_match_nav_open": True,
    }


@_bridge_view
@require_http_methods(["GET", "POST"])
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")

    ctx = _base_context(request, project)
    settings_ctx = match_bridge_service.get_settings_context(request.user, project)

    if request.method == "POST":
        if not settings_ctx["can_configure"]:
            messages.error(
                request,
                "No tiene permiso para configurar la integración FILE GATE.",
            )
            return redirect("file_match:bridge_hub", project_slug=project_slug)

        result = match_bridge_service.save_settings(
            request.user,
            project,
            {
                "file_gate_enabled": request.POST.get("file_gate_enabled") == "on",
                "file_gate_project_id": request.POST.get("file_gate_project_id", ""),
                "file_gate_accept": request.POST.get("file_gate_accept", ""),
                "file_gate_max_age_days": request.POST.get(
                    "file_gate_max_age_days", ""
                ),
                "file_gate_require_a": request.POST.get("file_gate_require_a") == "on",
                "file_gate_require_b": request.POST.get("file_gate_require_b") == "on",
            },
        )
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("file_match:bridge_hub", project_slug=project_slug)

        messages.error(request, result.user_message)
        settings_ctx = match_bridge_service.get_settings_context(request.user, project)
        settings_ctx["enabled"] = request.POST.get("file_gate_enabled") == "on"
        settings_ctx["gate_project_id"] = (
            request.POST.get("file_gate_project_id") or ""
        ).strip()
        settings_ctx["accept"] = (
            request.POST.get("file_gate_accept") or settings_ctx["accept"]
        ).strip()
        settings_ctx["max_age_days"] = request.POST.get("file_gate_max_age_days") or (
            settings_ctx["max_age_days"]
        )
        settings_ctx["require_a"] = request.POST.get("file_gate_require_a") == "on"
        settings_ctx["require_b"] = request.POST.get("file_gate_require_b") == "on"
        settings_ctx["errors"] = result.errors or {}
        ctx["bridge"] = settings_ctx
        return render(request, "file_match/bridge/hub.html", ctx)

    settings_ctx["errors"] = {}
    ctx["bridge"] = settings_ctx
    return render(request, "file_match/bridge/hub.html", ctx)


@_bridge_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project)
    return render(request, "file_match/bridge/hub_help.html", ctx)
