from django.contrib import messages
from django.shortcuts import redirect, render

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_match.history.services import match_history_service
from apps.file_match.projects.services import match_project_service
from apps.file_match.report.services import match_report_service as report_svc
from apps.projects.services import project_service


def _history_view(view_func):
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


@_history_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    if not report_svc.can_view_report(request.user, project):
        messages.error(
            request,
            "No tiene permiso para ver el historial de este proyecto.",
        )
        return redirect("file_match:project_list")

    ctx = _base_context(request, project)
    ctx["history"] = match_history_service.build_history_context(
        request.user, project, request.GET
    )
    return render(request, "file_match/history/hub.html", ctx)


@_history_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project)
    ctx["ttl_days"] = report_svc.REPORT_TTL.days
    return render(request, "file_match/history/hub_help.html", ctx)
