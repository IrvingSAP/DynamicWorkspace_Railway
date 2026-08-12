from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_split_merge.history.services import sm_history_service
from apps.file_split_merge.projects.services import split_merge_project_service
from apps.file_split_merge.run.services import sm_run_service
from apps.projects.services import project_service

MSG_NO_ACCESS = split_merge_project_service.MSG_NO_ACCESS


def _history_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = split_merge_project_service.get_project_for_user(request.user, project_slug)
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
        "app_nav_active": "file_split_merge",
        "file_split_merge_nav_open": True,
    }


@_history_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    if not sm_history_service.user_can_view_history(request.user, project):
        messages.error(request, sm_history_service.MSG_NO_PERMISSION)
        return redirect("file_split_merge:project_list")

    ctx = _base_context(request, project)
    ctx["history"] = sm_history_service.build_history_context(
        request.user, project, request.GET
    )
    return render(request, "file_split_merge/history/hub.html", ctx)


@_history_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    ctx = _base_context(request, project)
    ctx["ttl_days"] = sm_run_service.ARTIFACT_TTL.days
    return render(request, "file_split_merge/history/hub_help.html", ctx)


@_history_view
def detail(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    if not sm_history_service.user_can_view_history(request.user, project):
        messages.error(request, sm_history_service.MSG_NO_PERMISSION)
        return redirect("file_split_merge:project_list")

    job = sm_run_service.get_job(project, job_id)
    if job is None or job.status in sm_history_service.NON_FINAL_STATUSES:
        messages.error(request, sm_history_service.MSG_NOT_FOUND)
        return redirect("file_split_merge:history_hub", project_slug=project_slug)

    ctx = _base_context(request, project)
    ctx["detail"] = sm_history_service.build_detail_context(
        request.user, project, job
    )
    return render(request, "file_split_merge/history/detail.html", ctx)


@_history_view
def detail_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    job = sm_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, sm_history_service.MSG_NOT_FOUND)
        return redirect("file_split_merge:history_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["detail"] = sm_history_service.build_detail_context(
        request.user, project, job
    )
    ctx["ttl_days"] = sm_run_service.ARTIFACT_TTL.days
    return render(request, "file_split_merge/history/detail_help.html", ctx)


@_history_view
@require_POST
def delete_job(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")

    result = sm_history_service.delete_own_job(request.user, project, job_id)
    if result["ok"]:
        messages.success(request, result["user_message"])
    else:
        messages.error(request, result["user_message"])
    return redirect("file_split_merge:history_hub", project_slug=project.slug)


@_history_view
@require_POST
def delete_own_jobs(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")

    result = sm_history_service.delete_own_jobs(request.user, project)
    if result["ok"]:
        messages.success(request, result["user_message"])
    else:
        messages.error(request, result["user_message"])
    return redirect("file_split_merge:history_hub", project_slug=project.slug)
