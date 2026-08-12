from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_split_merge.projects.services import split_merge_project_service
from apps.file_split_merge.run.services import sm_run_service
from apps.projects.services import project_service

MSG_NO_ACCESS = split_merge_project_service.MSG_NO_ACCESS


def _run_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = split_merge_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return None
    return project


def _sidebar() -> dict:
    return {
        "app_nav_active": "file_split_merge",
        "file_split_merge_nav_open": True,
    }


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "membership": membership,
            "company": project.company,
        }
    )
    return ctx


def _collect_files(request):
    files = request.FILES.getlist("files")
    if files:
        return files
    single = request.FILES.get("file")
    return [single] if single else []


@_run_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    ctx = _base_context(request, project)
    ctx["run"] = sm_run_service.get_run_context(request.user, project)
    return render(request, "file_split_merge/run/hub.html", ctx)


@_run_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    ctx = _base_context(request, project)
    ctx["ttl_days"] = sm_run_service.ARTIFACT_TTL.days
    return render(request, "file_split_merge/run/hub_help.html", ctx)


def _execute(request, project, *, dry_run: bool):
    result = sm_run_service.run_sm_job(
        request.user,
        project,
        _collect_files(request),
        dry_run=dry_run,
        idempotency_key=(request.headers.get("Idempotency-Key") or "").strip() or None,
    )
    job = (result.payload or {}).get("job")
    if not result.ok:
        messages.error(request, result.user_message)
        for field_errors in (result.errors or {}).values():
            for msg in field_errors:
                messages.error(request, msg)
        if job is not None:
            return redirect(
                "file_split_merge:run_result",
                project_slug=project.slug,
                job_id=job.id,
            )
        return redirect("file_split_merge:run_hub", project_slug=project.slug)

    messages.success(request, result.user_message)
    return redirect(
        "file_split_merge:run_result",
        project_slug=project.slug,
        job_id=job.id,
    )


@_run_view
@require_http_methods(["POST"])
def run_execute(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    return _execute(request, project, dry_run=False)


@_run_view
@require_http_methods(["POST"])
def run_preview(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    return _execute(request, project, dry_run=True)


@_run_view
def run_result(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    job = sm_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, sm_run_service.MSG_JOB_NOT_FOUND)
        return redirect("file_split_merge:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = sm_run_service.build_job_view(project, job)
    ctx["run"] = {
        "can_execute": sm_run_service.user_can_execute(request.user, project),
        "can_download": sm_run_service.user_can_download(request.user, project),
    }
    return render(request, "file_split_merge/run/result.html", ctx)


@_run_view
def result_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    job = sm_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, sm_run_service.MSG_JOB_NOT_FOUND)
        return redirect("file_split_merge:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = sm_run_service.build_job_view(project, job)
    ctx["ttl_days"] = sm_run_service.ARTIFACT_TTL.days
    return render(request, "file_split_merge/run/result_help.html", ctx)


@_run_view
def run_download(request, project_slug: str, job_id, kind: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")

    job = sm_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, sm_run_service.MSG_JOB_NOT_FOUND)
        return redirect("file_split_merge:run_hub", project_slug=project_slug)

    auth = sm_run_service.authorize_download(request.user, project, job)
    if not auth.ok:
        messages.error(request, auth.user_message)
        return redirect(
            "file_split_merge:run_result",
            project_slug=project_slug,
            job_id=job.id,
        )

    resolved = sm_run_service.resolve_download(job, kind)
    if resolved is None:
        raise Http404()
    path, filename = resolved
    return FileResponse(path.open("rb"), as_attachment=True, filename=filename)
