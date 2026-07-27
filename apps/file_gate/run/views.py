from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_gate.projects.services import gate_project_service
from apps.file_gate.report.services import validation_report_service as report_svc
from apps.file_gate.run.services import validation_run_service
from apps.projects.services import project_service

DOWNLOAD_KINDS = {"report", "errors"}


def _run_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = gate_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE GATE.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    return {
        "project": project,
        "membership": membership,
        "company": project.company,
        "app_nav_active": "file_gate",
        "file_gate_nav_open": True,
    }


@_run_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project)
    ctx["run"] = validation_run_service.get_run_context(request.user, project)
    return render(request, "file_gate/run/hub.html", ctx)


@_run_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project)
    return render(request, "file_gate/run/hub_help.html", ctx)


@_run_view
def upload(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project)
    run = validation_run_service.get_run_context(request.user, project)
    if not run["has_published_version"]:
        messages.error(request, "Publique el contrato antes de validar.")
        return redirect("file_gate:run_hub", project_slug=project_slug)
    if not run["can_execute"]:
        messages.error(request, "No tiene permiso para validar archivos en este proyecto.")
        return redirect("file_gate:run_hub", project_slug=project_slug)
    ctx["run"] = run
    return render(request, "file_gate/run/upload.html", ctx)


@_run_view
@require_http_methods(["POST"])
def run_execute(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")

    result = validation_run_service.validate_and_run(
        request.user, project, request.FILES.get("file")
    )
    if not result.ok:
        messages.error(request, result.user_message)
        for field_errors in (result.errors or {}).values():
            for msg in field_errors:
                messages.error(request, msg)
        return redirect("file_gate:run_upload", project_slug=project_slug)

    job = result.payload["job"]
    messages.success(request, result.user_message)
    return redirect(
        "file_gate:run_result", project_slug=project_slug, job_id=job.id
    )


@_run_view
def run_result(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    job = validation_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la validación solicitada.")
        return redirect("file_gate:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["view"] = validation_run_service.build_job_view(project, job)
    ctx["run"] = {"can_execute": validation_run_service.user_can_execute(request.user, project)}
    if report_svc.is_job_final(job):
        ctx["report_url"] = reverse(
            "file_gate:report_detail",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        )
        ctx["certificate_url"] = reverse(
            "file_gate:report_certificate",
            kwargs={"project_slug": project.slug, "job_id": job.id},
        )
    return render(request, "file_gate/run/result.html", ctx)


@_run_view
def result_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    job = validation_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la validación solicitada.")
        return redirect("file_gate:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["job_id"] = job.id
    return render(request, "file_gate/run/result_help.html", ctx)


@_run_view
@require_http_methods(["GET"])
def run_download(request, project_slug: str, job_id, kind: str):
    """Descarga reforzada por Módulo 4: roles + TTL + processing_report."""
    project = gate_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        raise Http404()
    if kind not in DOWNLOAD_KINDS:
        raise Http404()
    job = validation_run_service.get_job(project, job_id)
    if job is None:
        raise Http404()

    result = report_svc.authorize_download(request.user, project, job, kind)
    if not result.ok:
        status = 403
        if result.error_code == "gone":
            status = 410
        elif result.error_code == "not_found":
            status = 404
        elif result.error_code == "validation_form":
            status = 400
        return JsonResponse(
            {"ok": False, "message": result.user_message},
            status=status,
        )

    path = result.payload["path"]
    filename = result.payload["filename"]
    content_type = (
        "application/json" if filename.endswith(".json") else "text/csv; charset=utf-8"
    )
    response = FileResponse(path.open("rb"), as_attachment=True, filename=filename)
    response["Content-Type"] = content_type
    return response
