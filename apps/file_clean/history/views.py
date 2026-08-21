from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_clean.history.services import clean_history_service
from apps.file_clean.projects.services import clean_project_service
from apps.file_clean.run.services import clean_run_service
from apps.projects.services import project_service

MSG_NO_ACCESS = clean_project_service.MSG_NO_ACCESS


def _history_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = clean_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    return {
        "project": project,
        "membership": membership,
        "company": project.company,
        "app_nav_active": "file_clean",
        "file_clean_nav_open": True,
        "lifecycle": clean_project_service.get_hub_context(request.user, project),
    }


@_history_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    if not clean_history_service.user_can_view_history(request.user, project):
        messages.error(request, clean_history_service.MSG_NO_PERMISSION)
        return redirect("file_clean:project_list")

    ctx = _base_context(request, project)
    ctx["history"] = clean_history_service.build_history_context(
        request.user, project, request.GET
    )
    return render(request, "file_clean/history/hub.html", ctx)


@_history_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    ctx = _base_context(request, project)
    ctx["ttl_days"] = clean_run_service.ARTIFACT_TTL.days
    return render(request, "file_clean/history/hub_help.html", ctx)


@_history_view
def detail(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    if not clean_history_service.user_can_view_history(request.user, project):
        messages.error(request, clean_history_service.MSG_NO_PERMISSION)
        return redirect("file_clean:project_list")

    job = clean_run_service.get_job(project, job_id)
    if job is None or job.status in clean_history_service.NON_FINAL_STATUSES:
        messages.error(request, clean_history_service.MSG_NOT_FOUND)
        return redirect("file_clean:history_hub", project_slug=project_slug)

    ctx = _base_context(request, project)
    ctx["detail"] = clean_history_service.build_detail_context(
        request.user, project, job
    )
    return render(request, "file_clean/history/detail.html", ctx)


@_history_view
def detail_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    job = clean_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, clean_history_service.MSG_NOT_FOUND)
        return redirect("file_clean:history_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["detail"] = clean_history_service.build_detail_context(
        request.user, project, job
    )
    ctx["ttl_days"] = clean_run_service.ARTIFACT_TTL.days
    return render(request, "file_clean/history/detail_help.html", ctx)


@_history_view
@require_POST
def delete_job(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")

    result = clean_history_service.delete_own_job(request.user, project, job_id)
    if result["ok"]:
        messages.success(request, result["user_message"])
    else:
        messages.error(request, result["user_message"])
    return redirect("file_clean:history_hub", project_slug=project.slug)


@_history_view
@require_POST
def delete_own_jobs(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")

    result = clean_history_service.delete_own_jobs(request.user, project)
    if result["ok"]:
        messages.success(request, result["user_message"])
    else:
        messages.error(request, result["user_message"])
    return redirect("file_clean:history_hub", project_slug=project.slug)
