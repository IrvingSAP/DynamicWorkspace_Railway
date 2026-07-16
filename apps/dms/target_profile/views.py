from django.contrib import messages
import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.mapping.services import mapping_project_service
from apps.dms.source_profile.services import version_publish_service
from apps.dms.target_profile.services import (
    target_persistence_service,
    target_profile_catalog_service,
    target_profile_service,
)
from apps.dms.target_profile.services import import_source_fields_service
from apps.projects.services import project_service

STEP4_TEMPLATES = {
    "fixed": "dms/target_profile/step4_fields.html",
    "delimited": "dms/target_profile/step4_fields_delimited.html",
    "xlsx": "dms/target_profile/step4_fields_xlsx.html",
    "json": "dms/target_profile/step4_fields_json.html",
    "xml": "dms/target_profile/step4_fields_xml.html",
}


def _target_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return None
    return project


def _base_context(request, project, current_step: int | None = None) -> dict:
    membership = project_service.get_membership(request.user, project)
    wizard = target_profile_service.get_wizard_context(project, membership)
    target = target_persistence_service.get_target_dict(project)
    return {
        "project": project,
        "wizard": wizard,
        "membership": membership,
        "current_step": current_step,
        "app_nav_active": "filepipe_mapping",
        "filepipe_nav_open": True,
        "target": target,
        "target_json": target_profile_service.target_context(project)["target_json"],
        "can_edit_target": target_persistence_service.user_can_edit_target(request.user, project),
        "target_save_url": reverse("dms:target_save", kwargs={"project_slug": project.slug}),
        "source_publish_url": reverse("dms:source_publish", kwargs={"project_slug": project.slug}),
        "version_publish": version_publish_service.get_publish_context(project),
    }


def _render(request, project_slug: str, template: str, current_step: int | None = None, **extra):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project, current_step)
    ctx.update(extra)
    return render(request, template, ctx)


@_target_view
def hub(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/hub.html")


@_target_view
def hub_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/hub_help.html")


@_target_view
def step1_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/step1_help.html", current_step=1)


@_target_view
def step2_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/step2_help.html", current_step=2)


@_target_view
def step3_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/step3_help.html", current_step=3)


@_target_view
def step4_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/step4_help.html", current_step=4)


@_target_view
def step5_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/step5_help.html", current_step=5)


@_target_view
def step6_help(request, project_slug: str):
    return _render(request, project_slug, "dms/target_profile/step6_help.html", current_step=6)


@_target_view
def step1_file_type(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project, current_step=1)
    ctx.update(target_profile_catalog_service.get_step1_catalog_context())
    return render(request, "dms/target_profile/step1_file_type.html", ctx)


@_target_view
def step2_encoding(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project, current_step=2)
    ctx.update(target_profile_catalog_service.get_step2_catalog_context())
    return render(request, "dms/target_profile/step2_encoding.html", ctx)


@_target_view
def step3_layout(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project, current_step=3)
    ctx.update(target_profile_service.get_step3_context(project))
    return render(request, "dms/target_profile/step3_layout.html", ctx)


@_target_view
def step4_fields(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")

    target = target_persistence_service.get_target_dict(project)
    variant = target_profile_service.get_step4_variant(target.get("file_type_code", ""))
    if variant == "unsupported":
        messages.warning(
            request,
            "El tipo de archivo seleccionado aún no tiene editor de campos. "
            "Elija txt_fixed, csv, txt_delimited, xlsx, json o xml en el paso 1.",
        )
        return redirect("dms:target_step1", project_slug=project_slug)

    ctx = _base_context(request, project, current_step=4)
    ctx.update(target_profile_service.get_step4_context(project, variant))
    ctx["target"] = target_persistence_service.get_target_dict(project)
    ctx["target_json"] = json.dumps(ctx["target"])
    return render(request, STEP4_TEMPLATES[variant], ctx)


@_target_view
@require_http_methods(["POST"])
def import_fields_from_source(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
            status=403,
        )

    result = import_source_fields_service.import_and_save_fields_from_source(
        request.user,
        project,
    )
    if result.ok:
        return JsonResponse(
            {
                "ok": True,
                "message": result.user_message,
                "fields": result.payload.get("fields") or [],
                "target": result.payload.get("target") or {},
                "warnings": result.payload.get("warning_messages") or [],
                "count": len(result.payload.get("fields") or []),
            }
        )
    status = 403 if result.error_code == "forbidden" else 400
    return JsonResponse(
        {
            "ok": False,
            "message": result.user_message,
            "errors": result.errors or {},
        },
        status=status,
    )


@_target_view
def step5_serialization(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project, current_step=5)
    ctx.update(target_profile_service.get_step5_context(project))
    return render(request, "dms/target_profile/step5_serialization.html", ctx)


@_target_view
def step6_write_validation(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project, current_step=6)
    ctx.update(target_profile_service.get_step6_context(project))
    return render(request, "dms/target_profile/step6_write_validation.html", ctx)


@_target_view
@require_http_methods(["POST"])
def target_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
                status=403,
            )
        return redirect("dms:mapping_list")

    payload: dict = {}
    raw = request.POST.get("target_payload", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "JSON de perfil inválido."},
                    status=400,
                )
            messages.error(request, "JSON de perfil inválido.")
            return redirect("dms:target_hub", project_slug=project_slug)

    strict = request.POST.get("strict", "") == "1"
    result = target_persistence_service.save_target(
        request.user,
        project,
        payload,
        strict=strict,
    )

    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse("dms:target_hub", kwargs={"project_slug": project_slug})

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
