import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.target_profile.services import (
    import_source_fields_service,
    target_persistence_service,
    target_profile_catalog_service,
    target_profile_service,
)
from apps.projects.services import project_service
from apps.reverse_studio.input.services import input_wizard_service
from apps.reverse_studio.output.services import output_wizard_service
from apps.reverse_studio.projects.services import reverse_project_service

STEP4_TEMPLATES = {
    "fixed": "reverse_studio/output/step4_fields.html",
    "json": "reverse_studio/output/step4_fields_json.html",
    "xml": "reverse_studio/output/step4_fields_xml.html",
}


def _output_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = reverse_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto Reverse Studio.")
        return None
    return project


def _base_context(request, project, current_step: int | None = None) -> dict:
    membership = project_service.get_membership(request.user, project)
    wizard = output_wizard_service.get_wizard_context(project, membership)
    target = target_persistence_service.get_target_dict(project)
    input_wizard = input_wizard_service.get_wizard_context(project, membership)
    return {
        "project": project,
        "wizard": wizard,
        "membership": membership,
        "current_step": current_step,
        "app_nav_active": "reverse_studio",
        "reverse_studio_nav_open": True,
        "target": target,
        "target_json": target_profile_service.target_context(project)["target_json"],
        "can_edit_target": target_persistence_service.user_can_edit_target(request.user, project),
        "target_save_url": reverse(
            "reverse_studio:output_save", kwargs={"project_slug": project.slug}
        ),
        "input_complete": input_wizard.steps_complete >= input_wizard.steps_total,
        "input_steps_complete": input_wizard.steps_complete,
        "input_steps_total": input_wizard.steps_total,
    }


def _render(request, project_slug: str, template: str, current_step: int | None = None, **extra):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project, current_step)
    ctx.update(extra)
    return render(request, template, ctx)


@_output_view
def hub(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/hub.html")


@_output_view
def hub_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/hub_help.html")


@_output_view
def step1_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/step1_help.html", current_step=1)


@_output_view
def step2_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/step2_help.html", current_step=2)


@_output_view
def step3_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/step3_help.html", current_step=3)


@_output_view
def step4_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/step4_help.html", current_step=4)


@_output_view
def step5_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/step5_help.html", current_step=5)


@_output_view
def step6_help(request, project_slug: str):
    return _render(request, project_slug, "reverse_studio/output/step6_help.html", current_step=6)


@_output_view
def step1_file_type(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project, current_step=1)
    ctx.update(output_wizard_service.get_step1_catalog_context())
    return render(request, "reverse_studio/output/step1_file_type.html", ctx)


@_output_view
def step2_encoding(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project, current_step=2)
    ctx.update(target_profile_catalog_service.get_step2_catalog_context())
    return render(request, "reverse_studio/output/step2_encoding.html", ctx)


@_output_view
def step3_layout(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project, current_step=3)
    ctx.update(target_profile_service.get_step3_context(project))
    return render(request, "reverse_studio/output/step3_layout.html", ctx)


@_output_view
def step4_fields(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")

    target = target_persistence_service.get_target_dict(project)
    variant = target_profile_service.get_step4_variant(target.get("file_type_code", ""))
    if variant not in STEP4_TEMPLATES:
        messages.warning(
            request,
            "Elija un tipo de layout permitido (TXT posicional, JSON o XML) en el paso 1.",
        )
        return redirect("reverse_studio:output_step1", project_slug=project_slug)

    ctx = _base_context(request, project, current_step=4)
    ctx.update(target_profile_service.get_step4_context(project, variant))
    ctx["target"] = target_persistence_service.get_target_dict(project)
    ctx["target_json"] = json.dumps(ctx["target"])
    return render(request, STEP4_TEMPLATES[variant], ctx)


@_output_view
@require_http_methods(["POST"])
def import_fields_from_input(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
            status=403,
        )

    result = import_source_fields_service.import_and_save_fields_from_source(
        request.user,
        project,
    )
    if result.ok:
        msg = result.user_message or "Campos cargados desde la entrada."
        msg = msg.replace("origen", "entrada").replace("Origen", "Entrada")
        return JsonResponse(
            {
                "ok": True,
                "message": msg,
                "fields": result.payload.get("fields") or [],
                "target": result.payload.get("target") or {},
                "warnings": result.payload.get("warning_messages") or [],
                "count": len(result.payload.get("fields") or []),
            }
        )
    status = 403 if result.error_code == "forbidden" else 400
    message = result.user_message or "No se pudieron cargar los campos."
    message = message.replace("origen", "entrada").replace("Origen", "Entrada")
    return JsonResponse(
        {
            "ok": False,
            "message": message,
            "errors": result.errors or {},
        },
        status=status,
    )


@_output_view
def step5_serialization(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project, current_step=5)
    ctx.update(target_profile_service.get_step5_context(project))
    return render(request, "reverse_studio/output/step5_serialization.html", ctx)


@_output_view
def step6_write_validation(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _base_context(request, project, current_step=6)
    ctx.update(target_profile_service.get_step6_context(project))
    return render(request, "reverse_studio/output/step6_write_validation.html", ctx)


@_output_view
@require_http_methods(["POST"])
def output_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
                status=403,
            )
        return redirect("reverse_studio:project_list")

    payload: dict = {}
    raw = request.POST.get("target_payload", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "JSON de contrato de salida inválido."},
                    status=400,
                )
            messages.error(request, "JSON de contrato de salida inválido.")
            return redirect("reverse_studio:output_hub", project_slug=project_slug)

    strict = request.POST.get("strict", "") == "1"
    result = target_persistence_service.save_target(
        request.user,
        project,
        payload,
        strict=strict,
    )

    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse("reverse_studio:output_hub", kwargs={"project_slug": project_slug})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "target": result.payload.get("target", {}),
                    "warnings": result.payload.get("warning_messages") or [],
                }
            )
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
                "warnings": target_persistence_service.flatten_validation_messages(
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
