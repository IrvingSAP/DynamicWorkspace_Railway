from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_gate.bridge.services import dms_bridge_service
from apps.projects.services import project_service
from apps.reverse_studio.projects.services import reverse_project_service


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
    return {
        "project": project,
        "membership": membership,
        **_sidebar(),
    }


@_rs_view
@require_http_methods(["GET", "POST"])
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")

    ctx = _base_context(request, project)
    settings_ctx = dms_bridge_service.get_settings_context(request.user, project)

    if request.method == "POST":
        if not settings_ctx["can_configure"]:
            messages.error(
                request, "No tiene permiso para configurar la integración FILE GATE."
            )
            return redirect("reverse_studio:bridge_hub", project_slug=project_slug)

        result = dms_bridge_service.save_settings(
            request.user,
            project,
            {
                "file_gate_enabled": request.POST.get("file_gate_enabled") == "on",
                "file_gate_project_id": request.POST.get("file_gate_project_id", ""),
                "file_gate_accept": request.POST.get("file_gate_accept", ""),
                "file_gate_max_age_days": request.POST.get("file_gate_max_age_days", ""),
            },
        )
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("reverse_studio:bridge_hub", project_slug=project_slug)

        messages.error(request, result.user_message)
        settings_ctx = dms_bridge_service.get_settings_context(request.user, project)
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
        settings_ctx["errors"] = result.errors or {}
        ctx["bridge"] = settings_ctx
        return render(request, "reverse_studio/bridge/hub.html", ctx)

    settings_ctx["errors"] = {}
    ctx["bridge"] = settings_ctx
    return render(request, "reverse_studio/bridge/hub.html", ctx)


@_rs_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project)
    return render(request, "reverse_studio/bridge/hub_help.html", ctx)
