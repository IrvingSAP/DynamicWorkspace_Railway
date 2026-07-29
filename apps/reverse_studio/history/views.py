from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.transform_execution.constants import DOWNLOAD_TTL
from apps.projects.models import ProjectMembership
from apps.projects.services import project_service
from apps.reverse_studio.history.services import history_service
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
    return {
        "project": project,
        "membership": membership,
        **_sidebar(),
    }


@_rs_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    if not history_service.user_can_view_history(request.user, project):
        messages.error(request, "No tiene permiso para ver el historial de este proyecto.")
        return redirect("reverse_studio:project_list")

    ctx = _base_context(request, project)
    ctx["history"] = history_service.build_history_context(
        request.user, project, request.GET
    )
    return render(request, "reverse_studio/history/hub.html", ctx)


@_rs_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project)
    ctx["ttl_days"] = DOWNLOAD_TTL.days
    return render(request, "reverse_studio/history/hub_help.html", ctx)


@_rs_view
def detail(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    if not history_service.user_can_view_history(request.user, project):
        messages.error(request, "No tiene permiso para ver el historial de este proyecto.")
        return redirect("reverse_studio:project_list")

    row = history_service.get_job_detail(request.user, project, job_id)
    if row is None:
        raise Http404()

    membership = project_service.get_membership(request.user, project)
    ctx = _base_context(request, project)
    ctx["job_row"] = row
    ctx["can_download"] = generate_run_service.user_can_download(request.user, project)
    ctx["is_consulta"] = (
        membership is None or membership.role == ProjectMembership.ROLE_CO
    )
    ctx["ttl_days"] = DOWNLOAD_TTL.days
    return render(request, "reverse_studio/history/detail.html", ctx)
