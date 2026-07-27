import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.source_profile.services import source_persistence_service
from apps.file_gate.policy.services import gate_policy_service
from apps.file_gate.projects.services import gate_project_service
from apps.file_gate.schema.services import schema_publish_service
from apps.projects.services import project_service


def _policy_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = gate_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE GATE.")
        return None
    return project


def _base_context(request, project, current_step: int | None = None) -> dict:
    membership = project_service.get_membership(request.user, project)
    wizard = gate_policy_service.get_wizard_context(project, membership)
    return {
        "project": project,
        "wizard": wizard,
        "policy": wizard.policy,
        "membership": membership,
        "current_step": current_step,
        "app_nav_active": "file_gate",
        "file_gate_nav_open": True,
        "can_edit_source": source_persistence_service.user_can_edit_source(
            request.user, project
        ),
        "source_publish_url": reverse(
            "file_gate:schema_publish", kwargs={"project_slug": project.slug}
        ),
        "policy_save_url": reverse(
            "file_gate:policy_save", kwargs={"project_slug": project.slug}
        ),
        "version_publish": schema_publish_service.get_publish_context(project),
    }


@_policy_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project)
    return render(request, "file_gate/policy/hub.html", ctx)


@_policy_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project)
    return render(request, "file_gate/policy/hub_help.html", ctx)


@_policy_view
def step1_collection(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project, current_step=1)
    return render(request, "file_gate/policy/step1_collection.html", ctx)


@_policy_view
def step1_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project, current_step=1)
    return render(request, "file_gate/policy/step1_help.html", ctx)


@_policy_view
def step2_threshold(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project, current_step=2)
    return render(request, "file_gate/policy/step2_threshold.html", ctx)


@_policy_view
def step2_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project, current_step=2)
    return render(request, "file_gate/policy/step2_help.html", ctx)


@_policy_view
def step3_review(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project, current_step=3)
    ctx["policy_json"] = json.dumps(ctx["policy"], indent=2, ensure_ascii=False)
    return render(request, "file_gate/policy/step3_review.html", ctx)


@_policy_view
def step3_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_gate:project_list")
    ctx = _base_context(request, project, current_step=3)
    return render(request, "file_gate/policy/step3_help.html", ctx)


def _parse_policy_payload(request) -> dict:
    raw = request.POST.get("policy_payload", "").strip()
    if raw:
        return json.loads(raw)

    partial: dict = {}
    if "on_error" in request.POST:
        partial["on_error"] = request.POST.get("on_error", "").strip()
    if "max_errors" in request.POST:
        partial["max_errors"] = request.POST.get("max_errors")
    # MVP: fatal siempre true
    partial["abort_on_first_fatal"] = True

    mode = request.POST.get("reject_threshold_mode", "").strip()
    value = request.POST.get("reject_threshold_value", "").strip()
    if mode or value:
        threshold = dict((gate_policy_service.default_gate_policy().get("reject_threshold") or {}))
        if mode:
            threshold["mode"] = mode
        if value != "":
            threshold["value"] = value
        partial["reject_threshold"] = threshold
    return partial


@_policy_view
@require_http_methods(["POST"])
def policy_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto FILE GATE."},
                status=403,
            )
        return redirect("file_gate:project_list")

    try:
        partial = _parse_policy_payload(request)
    except json.JSONDecodeError:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "JSON de política inválido."},
                status=400,
            )
        messages.error(request, "JSON de política inválido.")
        return redirect("file_gate:policy_hub", project_slug=project_slug)

    result = gate_policy_service.save_gate_policy(request.user, project, partial)
    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse("file_gate:policy_hub", kwargs={"project_slug": project_slug})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "gate_policy": result.payload.get("gate_policy", {}),
                    "warnings": result.payload.get("warning_messages") or [],
                }
            )
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
                "warnings": source_persistence_service.flatten_validation_messages(
                    getattr(result, "warnings", None)
                    or (result.payload or {}).get("warnings")
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
