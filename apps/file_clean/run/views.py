from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_clean.projects.services import clean_project_service
from apps.file_clean.run.services import clean_run_service
from apps.projects.services import project_service

DOWNLOAD_KINDS = {"output", "change_log", "change_log_json", "change_log_csv"}

MSG_NO_ACCESS = clean_project_service.MSG_NO_ACCESS


def _run_view(view_func):
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
    }


@_run_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    ctx = _base_context(request, project)
    ctx["run"] = clean_run_service.get_run_context(request.user, project)
    return render(request, "file_clean/run/hub.html", ctx)


@_run_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    ctx = _base_context(request, project)
    ctx["ttl_days"] = clean_run_service.ARTIFACT_TTL.days
    return render(request, "file_clean/run/hub_help.html", ctx)


def _execute(request, project, *, dry_run: bool):
    result = clean_run_service.run_clean_job(
        request.user,
        project,
        None,
        request.FILES.get("file"),
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
                "file_clean:run_result",
                project_slug=project.slug,
                job_id=job.id,
            )
        return redirect("file_clean:run_hub", project_slug=project.slug)

    messages.success(request, result.user_message)
    return redirect(
        "file_clean:run_result",
        project_slug=project.slug,
        job_id=job.id,
    )


@_run_view
@require_http_methods(["POST"])
def run_execute(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    return _execute(request, project, dry_run=False)


@_run_view
@require_http_methods(["POST"])
def run_preview(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    return _execute(request, project, dry_run=True)


@_run_view
def run_result(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    job = clean_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, clean_run_service.MSG_JOB_NOT_FOUND)
        return redirect("file_clean:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = clean_run_service.build_job_view(project, job)
    ctx["run"] = {
        "can_execute": clean_run_service.user_can_execute(request.user, project),
        "can_download": clean_run_service.user_can_download(request.user, project),
    }
    return render(request, "file_clean/run/result.html", ctx)


@_run_view
def result_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    job = clean_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, clean_run_service.MSG_JOB_NOT_FOUND)
        return redirect("file_clean:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = clean_run_service.build_job_view(project, job)
    ctx["ttl_days"] = clean_run_service.ARTIFACT_TTL.days
    return render(request, "file_clean/run/result_help.html", ctx)


@_run_view
def run_download(request, project_slug: str, job_id, kind: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    if kind not in DOWNLOAD_KINDS:
        raise Http404()

    job = clean_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, clean_run_service.MSG_JOB_NOT_FOUND)
        return redirect("file_clean:run_hub", project_slug=project_slug)

    if not clean_run_service.user_can_download(request.user, project):
        messages.error(request, clean_run_service.MSG_FORBIDDEN)
        return redirect(
            "file_clean:run_result",
            project_slug=project_slug,
            job_id=job.id,
        )

    auth = clean_run_service.authorize_download(request.user, project, job)
    if not auth.ok:
        messages.error(request, auth.user_message)
        return redirect(
            "file_clean:run_result",
            project_slug=project_slug,
            job_id=job.id,
        )

    stored, filename = clean_run_service.resolve_download(job, kind)
    if not stored:
        messages.error(request, clean_run_service.MSG_DOWNLOAD_BAD)
        return redirect(
            "file_clean:run_result",
            project_slug=project_slug,
            job_id=job.id,
        )

    path = clean_run_service.resolve_download_path(job, kind)
    if path is None:
        messages.error(request, clean_run_service.MSG_DOWNLOAD_GONE)
        return redirect(
            "file_clean:run_result",
            project_slug=project_slug,
            job_id=job.id,
        )

    if kind in {"change_log", "change_log_json"}:
        content_type = "application/json"
    elif kind == "change_log_csv":
        content_type = "text/csv; charset=utf-8"
    elif path.suffix.lower() == ".json":
        content_type = "application/json"
    elif path.suffix.lower() in {".csv", ".txt"}:
        content_type = "text/plain; charset=utf-8"
    elif path.suffix.lower() == ".xlsx":
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        content_type = "application/octet-stream"

    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=filename,
        content_type=content_type,
    )
