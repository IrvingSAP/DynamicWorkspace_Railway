import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.source_profile.services import source_persistence_service, source_profile_catalog_service
from apps.dms.source_profile.services import source_profile_service
from apps.file_match.profile_b.services import (
    profile_b_persistence_service,
    profile_b_wizard_service,
)
from apps.file_match.projects.services import match_project_service
from apps.projects.services import project_service

STEP4_TEMPLATES = {
    "fixed": "file_match/profile_b/step4_fields.html",
    "delimited": "file_match/profile_b/step4_fields_delimited.html",
    "xlsx": "file_match/profile_b/step4_fields_xlsx.html",
    "json": "file_match/profile_b/step4_fields_json.html",
    "xml": "file_match/profile_b/step4_fields_xml.html",
}


def _profile_b_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = match_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE MATCH.")
        return None
    return project


def _base_context(request, project, current_step: int | None = None) -> dict:
    membership = project_service.get_membership(request.user, project)
    wizard = profile_b_wizard_service.get_wizard_context(project, membership)
    source = profile_b_persistence_service.get_source_b_dict(project)
    return {
        "project": project,
        "wizard": wizard,
        "membership": membership,
        "current_step": current_step,
        "app_nav_active": "file_match",
        "file_match_nav_open": True,
        "source": source,
        "source_json": json.dumps(source),
        "can_edit_source": source_persistence_service.user_can_edit_source(request.user, project),
        "source_save_url": reverse(
            "file_match:profile_b_save", kwargs={"project_slug": project.slug}
        ),
    }


def _render(request, project_slug: str, template: str, current_step: int | None = None, **extra):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project, current_step)
    ctx.update(extra)
    return render(request, template, ctx)


@_profile_b_view
def hub(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/hub.html")


@_profile_b_view
def hub_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/hub_help.html")


@_profile_b_view
def step1_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/step1_help.html", current_step=1)


@_profile_b_view
def step2_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/step2_help.html", current_step=2)


@_profile_b_view
def step3_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/step3_help.html", current_step=3)


@_profile_b_view
def step4_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/step4_help.html", current_step=4)


@_profile_b_view
def step5_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/step5_help.html", current_step=5)


@_profile_b_view
def step6_help(request, project_slug: str):
    return _render(request, project_slug, "file_match/profile_b/step6_help.html", current_step=6)


@_profile_b_view
def step1_file_type(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project, current_step=1)
    ctx.update(profile_b_wizard_service.get_step1_catalog_context())
    return render(request, "file_match/profile_b/step1_file_type.html", ctx)


@_profile_b_view
def step2_capture_start(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project, current_step=2)
    ctx.update(source_profile_catalog_service.get_step2_catalog_context())
    return render(request, "file_match/profile_b/step2_capture_start.html", ctx)


@_profile_b_view
def step3_capture_end(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project, current_step=3)
    ctx.update(source_profile_catalog_service.get_step3_catalog_context())
    return render(request, "file_match/profile_b/step3_capture_end.html", ctx)


@_profile_b_view
def step4_fields(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")

    source = profile_b_persistence_service.get_source_b_dict(project)
    variant = source_profile_service.get_step4_variant(source.get("file_type_code", ""))
    if variant == "unsupported" or variant not in STEP4_TEMPLATES:
        messages.warning(
            request,
            "Elija un tipo de archivo permitido (CSV, Excel, TXT delimitado, "
            "TXT posicional, JSON o XML) en el paso 1.",
        )
        return redirect("file_match:profile_b_step1", project_slug=project_slug)

    ctx = _base_context(request, project, current_step=4)
    ctx.update(profile_b_wizard_service.get_step4_context(project, variant))
    ctx["source"] = profile_b_persistence_service.get_source_b_dict(project)
    ctx["source_json"] = json.dumps(ctx["source"])
    return render(request, STEP4_TEMPLATES[variant], ctx)


@_profile_b_view
def step5_content_rules(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project, current_step=5)
    ctx.update(profile_b_wizard_service.get_step5_content_rules_context(project))
    return render(request, "file_match/profile_b/step5_content_rules.html", ctx)


@_profile_b_view
def step6_report(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    ctx = _base_context(request, project, current_step=6)
    ctx.update(profile_b_wizard_service.get_step6_report_context(project))
    return render(request, "file_match/profile_b/step6_report.html", ctx)


@_profile_b_view
@require_http_methods(["POST"])
def profile_b_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto FILE MATCH."},
                status=403,
            )
        return redirect("file_match:project_list")

    payload: dict = {}
    raw = request.POST.get("source_payload", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "JSON de perfil B inválido."},
                    status=400,
                )
            messages.error(request, "JSON de perfil B inválido.")
            return redirect("file_match:profile_b_hub", project_slug=project_slug)
    else:
        for key in (
            "file_type_code",
            "encoding_code",
            "encoding_custom",
            "line_ending_code",
            "line_ending_custom",
        ):
            if key in request.POST:
                payload[key] = request.POST.get(key, "").strip()
        if "capture_start_mode" in request.POST:
            mode = request.POST.get("capture_start_mode", "").strip()
            capture_start = {"mode": mode}
            if mode == "line_number":
                capture_start["line"] = int(request.POST.get("start_line", "1") or 1)
            elif mode == "after_header_block":
                capture_start["skip_lines"] = int(request.POST.get("skip_lines", "0") or 0)
            elif mode == "marker_start":
                capture_start["marker"] = request.POST.get("marker_start", "").strip()
            elif mode == "after_pattern":
                capture_start["pattern"] = request.POST.get("start_pattern", "").strip()
            elif mode == "after_blank_run":
                try:
                    capture_start["blank_count"] = int(
                        request.POST.get("start_blank_count", "1") or 1
                    )
                except (TypeError, ValueError):
                    capture_start["blank_count"] = 1
            payload["capture_start"] = capture_start
        if "capture_end_mode" in request.POST:
            mode = request.POST.get("capture_end_mode", "").strip()
            capture_end = {"mode": mode}
            if mode == "line_number":
                capture_end["line"] = int(request.POST.get("end_line", "1") or 1)
            elif mode == "percent":
                capture_end["value"] = int(request.POST.get("percent_value", "80") or 80)
            elif mode == "max_rows":
                capture_end["max_rows"] = int(request.POST.get("max_rows", "1000") or 1000)
            elif mode == "marker_end":
                capture_end["marker"] = request.POST.get("marker_end", "").strip()
            elif mode == "line_or_eof":
                capture_end["line"] = int(request.POST.get("line_or_eof", "1") or 1)
            elif mode == "before_pattern":
                capture_end["pattern"] = request.POST.get("end_pattern", "").strip()
            elif mode == "blank_run":
                try:
                    capture_end["blank_count"] = int(
                        request.POST.get("end_blank_count", "1") or 1
                    )
                except (TypeError, ValueError):
                    capture_end["blank_count"] = 1
            payload["capture_end"] = capture_end

    strict = request.POST.get("strict", "") == "1"
    result = profile_b_persistence_service.save_source_b(
        request.user,
        project,
        payload,
        strict=strict,
    )

    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse("file_match:profile_b_hub", kwargs={"project_slug": project_slug})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "source": result.payload.get("source", {}),
                    "warnings": result.payload.get("warning_messages") or [],
                }
            )
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
                "warnings": source_persistence_service.flatten_validation_messages(
                    (result.payload or {}).get("warnings")
                ),
            },
            status=400,
        )

    if result.ok:
        messages.success(request, result.user_message)
        for warning in result.payload.get("warning_messages") or []:
            messages.warning(request, warning)
    else:
        messages.error(request, result.user_message)
    return redirect(redirect_to)
