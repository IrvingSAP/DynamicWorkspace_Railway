import json

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.file_match.projects.services import match_project_service
from apps.file_match.report.services import match_report_service as report_svc
from apps.file_match.run.services import match_run_service
from apps.projects.services import project_service


def _report_view(view_func):
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


@_report_view
def detail(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    if not report_svc.can_view_report(request.user, project):
        messages.error(request, "No tiene permiso para ver la evidencia.")
        return redirect("file_match:project_list")

    job = match_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la conciliación solicitada.")
        return redirect("file_match:run_hub", project_slug=project_slug)
    if not report_svc.is_job_final(job):
        messages.warning(request, "La conciliación aún no finalizó.")
        return redirect("file_match:run_hub", project_slug=project_slug)

    reveal = request.GET.get("reveal") == "1"
    bucket = (request.GET.get("bucket") or "").strip()
    ctx = _base_context(request, project)
    ctx["view"] = report_svc.build_report_view(
        request.user, project, job, bucket=bucket, reveal=reveal
    )
    ctx["result_url"] = reverse(
        "file_match:run_result",
        kwargs={"project_slug": project.slug, "job_id": job.id},
    )
    return render(request, "file_match/report/detail.html", ctx)


@_report_view
def detail_help(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    job = match_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la conciliación solicitada.")
        return redirect("file_match:run_hub", project_slug=project_slug)
    ctx = _base_context(request, project)
    ctx["job_id"] = str(job.id)
    return render(request, "file_match/report/detail_help.html", ctx)


@_report_view
def certificate(request, project_slug: str, job_id):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    if not report_svc.can_view_certificate(request.user, project):
        messages.error(request, "No tiene permiso para ver el certificado.")
        return redirect("file_match:project_list")

    job = match_run_service.get_job(project, job_id)
    if job is None:
        messages.error(request, "No se encontró la conciliación solicitada.")
        return redirect("file_match:run_hub", project_slug=project_slug)
    if not report_svc.is_job_final(job):
        messages.warning(request, "La conciliación aún no finalizó.")
        return redirect("file_match:run_hub", project_slug=project_slug)

    ctx = _base_context(request, project)
    cert = report_svc.build_certificate(request.user, project, job)
    ctx["cert"] = cert
    ctx["cert_json"] = json.dumps(
        report_svc.certificate_json_payload(cert), indent=2, ensure_ascii=False
    )
    ctx["report_url"] = reverse(
        "file_match:report_detail",
        kwargs={"project_slug": project.slug, "job_id": job.id},
    )
    ctx["certificate_download_url"] = reverse(
        "file_match:report_certificate_download",
        kwargs={"project_slug": project.slug, "job_id": job.id},
    )
    return render(request, "file_match/report/certificate.html", ctx)


@_report_view
@require_http_methods(["GET"])
def certificate_download(request, project_slug: str, job_id):
    project = match_project_service.get_project_for_user(request.user, project_slug)
    if project is None or not report_svc.can_view_certificate(request.user, project):
        raise Http404()
    job = match_run_service.get_job(project, job_id)
    if job is None or not report_svc.is_job_final(job):
        raise Http404()
    cert = report_svc.build_certificate(request.user, project, job)
    payload = report_svc.certificate_json_payload(cert)
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="match_certificate_{str(job.id)[:8]}.json"'
    )
    return response
