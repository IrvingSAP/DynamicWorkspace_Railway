from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_match.projects.services import match_project_service
from apps.file_match.run.services import match_run_service
from apps.projects.services import project_service

DOWNLOAD_KINDS = {"report", "diff"}


def _run_view(view_func):
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


@_run_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project)
    ctx["run"] = match_run_service.get_run_context(request.user, project)
    return render(request, "file_match/run/hub.html", ctx)


@_run_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project)
    return render(request, "file_match/run/hub_help.html", ctx)


@_run_view
@require_http_methods(["POST"])
def run_execute(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")

    result = match_run_service.match_and_run(
        request.user,
        project,
        request.FILES.get("file_a"),
        request.FILES.get("file_b"),
    )
    if not result.ok:
        messages.error(request, result.user_message)
        for field_errors in (result.errors or {}).values():
            for msg in field_errors:
                messages.error(request, msg)
        return redirect("file_match:run_hub", project_slug=project_slug)

    job = result.payload["job"]
    messages.success(request, result.user_message)
    return redirect(
        "file_match:run_result",
        project_slug=project_slug,
        job_id=job.id,
    )


@_run_view
def run_result(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    job = match_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la conciliación solicitada.")
        return redirect("file_match:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = match_run_service.build_job_view(project, job)
    ctx["run"] = {
        "can_execute": match_run_service.user_can_execute(request.user, project),
        "can_download": match_run_service.user_can_download_detail(request.user, project),
    }
    return render(request, "file_match/run/result.html", ctx)


@_run_view
def result_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    job = match_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la conciliación solicitada.")
        return redirect("file_match:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = match_run_service.build_job_view(project, job)
    return render(request, "file_match/run/result_help.html", ctx)


@_run_view
def run_download(request, project_slug: str, job_id, kind: str):
    from apps.file_match.report.services import match_report_service as report_svc

    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    if kind not in DOWNLOAD_KINDS:
        raise Http404()

    job = match_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la conciliación solicitada.")
        return redirect("file_match:run_hub", project_slug=project_slug)

    auth = report_svc.authorize_download(request.user, project, job)
    if not auth.ok:
        messages.error(request, auth.user_message)
        return redirect(
            "file_match:report_detail",
            project_slug=project_slug,
            job_id=job.id,
        )

    path = match_run_service.resolve_download_path(job, kind)
    if path is None:
        messages.error(request, "El archivo de descarga no está disponible.")
        return redirect(
            "file_match:run_result",
            project_slug=project_slug,
            job_id=job.id,
        )

    content_type = "application/json" if kind == "report" else "text/csv; charset=utf-8"
    filename = "match_report.json" if kind == "report" else "match_diff.csv"
    return FileResponse(path.open("rb"), as_attachment=True, filename=filename, content_type=content_type)
