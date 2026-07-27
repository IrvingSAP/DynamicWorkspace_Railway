"""Vistas DMS para la integración FILE GATE (config del bridge)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.mapping.services import mapping_project_service
from apps.file_gate.bridge.services import dms_bridge_service
from apps.projects.services import project_service


def _dms_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    return {
        "project": project,
        "membership": membership,
        "app_nav_active": "filepipe_mapping",
        "filepipe_nav_open": True,
    }


@_dms_view
@require_http_methods(["GET", "POST"])
def settings(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")

    ctx = _base_context(request, project)
    settings_ctx = dms_bridge_service.get_settings_context(request.user, project)

    if request.method == "POST":
        if not settings_ctx["can_configure"]:
            messages.error(
                request, "No tiene permiso para configurar la integración FILE GATE."
            )
            return redirect("dms:file_gate_bridge_settings", project_slug=project_slug)

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
            return redirect("dms:file_gate_bridge_settings", project_slug=project_slug)

        messages.error(request, result.user_message)
        settings_ctx = dms_bridge_service.get_settings_context(request.user, project)
        # Rehydrate posted values for inline errors.
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
        return render(request, "dms/file_gate_bridge/settings.html", ctx)

    settings_ctx["errors"] = {}
    ctx["bridge"] = settings_ctx
    return render(request, "dms/file_gate_bridge/settings.html", ctx)


@_dms_view
def settings_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project)
    return render(request, "dms/file_gate_bridge/settings_help.html", ctx)
