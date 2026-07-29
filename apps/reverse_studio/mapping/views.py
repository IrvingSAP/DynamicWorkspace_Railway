import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.field_mapping.services import (
    field_mapping_persistence_service,
    field_mapping_preview_service,
    field_mapping_service,
)
from apps.dms.source_profile.services import version_publish_service
from apps.dms.transform_rules.services import (
    transform_rules_persistence_service,
    transform_rules_service,
)
from apps.projects.services import project_service
from apps.reverse_studio.input.services import input_wizard_service
from apps.reverse_studio.mapping.services import mapping_hub_service
from apps.reverse_studio.output.services import output_wizard_service
from apps.reverse_studio.projects.services import reverse_project_service


def _rs_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = reverse_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto Reverse Studio.")
        return None
    return project


def _sidebar() -> dict:
    return {
        "app_nav_active": "reverse_studio",
        "reverse_studio_nav_open": True,
    }


def _prereq_flags(project, membership) -> dict:
    input_wizard = input_wizard_service.get_wizard_context(project, membership)
    output_wizard = output_wizard_service.get_wizard_context(project, membership)
    return {
        "input_complete": input_wizard.steps_complete >= input_wizard.steps_total,
        "input_steps_complete": input_wizard.steps_complete,
        "input_steps_total": input_wizard.steps_total,
        "output_complete": output_wizard.steps_complete >= output_wizard.steps_total,
        "output_steps_complete": output_wizard.steps_complete,
        "output_steps_total": output_wizard.steps_total,
    }


def _mapping_base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    editor = field_mapping_service.get_editor_context(project, membership)
    summary = mapping_hub_service.get_mapping_hub_summary(project, membership)
    ctx = {
        "project": project,
        "membership": membership,
        "can_edit_mappings": field_mapping_persistence_service.user_can_edit_mappings(
            request.user, project
        ),
        "mapping_save_url": reverse(
            "reverse_studio:mapping_save", kwargs={"project_slug": project.slug}
        ),
        "mapping_preview_url": reverse(
            "reverse_studio:mapping_preview", kwargs={"project_slug": project.slug}
        ),
        "version_publish": version_publish_service.get_publish_context(project),
        "mapping_summary": summary,
        **_sidebar(),
        **_prereq_flags(project, membership),
        **editor,
    }
    return ctx


def _rules_base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    editor = transform_rules_service.get_editor_context(project, membership)
    return {
        "project": project,
        "membership": membership,
        "can_edit_rules": transform_rules_persistence_service.user_can_edit_rules(
            request.user, project
        ),
        "rules_save_url": reverse(
            "reverse_studio:mapping_rules_save", kwargs={"project_slug": project.slug}
        ),
        "rules_preview_url": reverse(
            "reverse_studio:mapping_rules_preview", kwargs={"project_slug": project.slug}
        ),
        "version_publish": version_publish_service.get_publish_context(project),
        **_sidebar(),
        **_prereq_flags(project, membership),
        **editor,
    }


@_rs_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/mapping/hub.html",
        _mapping_base_context(request, project),
    )


@_rs_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/mapping/hub_help.html",
        _mapping_base_context(request, project),
    )


@_rs_view
def editor(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _mapping_base_context(request, project)
    if not ctx["source_fields"] or not ctx["target_fields"]:
        messages.warning(
            request,
            "Complete primero el contrato de entrada y el de salida antes de mapear campos.",
        )
        if not ctx["source_fields"]:
            return redirect("reverse_studio:input_hub", project_slug=project_slug)
        return redirect("reverse_studio:output_hub", project_slug=project_slug)
    return render(request, "reverse_studio/mapping/editor.html", ctx)


@_rs_view
def editor_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/mapping/editor_help.html",
        _mapping_base_context(request, project),
    )


@_rs_view
@require_http_methods(["POST"])
def mapping_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
                status=403,
            )
        return redirect("reverse_studio:project_list")

    payload: dict = {}
    raw = request.POST.get("mappings_payload", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "JSON de mapeo inválido."},
                    status=400,
                )
            messages.error(request, "JSON de mapeo inválido.")
            return redirect("reverse_studio:mapping_editor", project_slug=project_slug)

    if "mappings" not in payload and isinstance(payload, list):
        payload = {"mappings": payload}

    strict = request.POST.get("strict", "") == "1"
    result = field_mapping_persistence_service.save_mappings(
        request.user,
        project,
        payload,
        strict=strict,
    )

    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse(
            "reverse_studio:mapping_editor", kwargs={"project_slug": project_slug}
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "mappings": result.payload.get("mappings", []),
                    "warnings": result.payload.get("warning_messages") or [],
                }
            )
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
                "warnings": field_mapping_persistence_service.flatten_validation_messages(
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


@_rs_view
@require_http_methods(["POST"])
def mapping_preview(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
            status=403,
        )

    mappings = []
    raw_mappings = request.POST.get("mappings_payload", "").strip()
    if raw_mappings:
        try:
            payload = json.loads(raw_mappings)
            if isinstance(payload, list):
                mappings = payload
            else:
                mappings = payload.get("mappings") or []
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "message": "JSON de mapeo inválido."},
                status=400,
            )

    source_row = {}
    raw_row = request.POST.get("source_row", "").strip()
    if raw_row:
        try:
            parsed = json.loads(raw_row)
            if isinstance(parsed, dict):
                source_row = parsed
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "message": "JSON de fila de entrada inválido."},
                status=400,
            )

    try:
        row_number = int(request.POST.get("row_number") or 1)
    except (TypeError, ValueError):
        row_number = 1

    result = field_mapping_preview_service.preview_mappings(
        project,
        mappings=mappings,
        source_row=source_row,
        row_number=row_number,
    )
    if result.ok:
        return JsonResponse(
            {
                "ok": True,
                "message": result.user_message,
                "target_row": result.payload.get("target_row") or {},
                "row_errors": result.payload.get("row_errors") or [],
                "source_row": result.payload.get("source_row") or {},
            }
        )
    return JsonResponse(
        {
            "ok": False,
            "message": result.user_message,
            "errors": result.errors or {},
        },
        status=400,
    )


@_rs_view
def rules_hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/mapping/rules/hub.html",
        _rules_base_context(request, project),
    )


@_rs_view
def rules_hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/mapping/rules/hub_help.html",
        _rules_base_context(request, project),
    )


@_rs_view
def rules_editor(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    ctx = _rules_base_context(request, project)
    if not ctx["rule_rows"]:
        messages.warning(
            request,
            "Defina al menos un enlace de mapeo antes de configurar reglas de transformación.",
        )
        return redirect("reverse_studio:mapping_hub", project_slug=project_slug)
    return render(request, "reverse_studio/mapping/rules/editor.html", ctx)


@_rs_view
def rules_editor_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("reverse_studio:project_list")
    return render(
        request,
        "reverse_studio/mapping/rules/editor_help.html",
        _rules_base_context(request, project),
    )


@_rs_view
@require_http_methods(["POST"])
def rules_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
                status=403,
            )
        return redirect("reverse_studio:project_list")

    pipelines: dict = {}
    raw = request.POST.get("pipelines_payload", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "JSON de reglas inválido."},
                    status=400,
                )
            messages.error(request, "JSON de reglas inválido.")
            return redirect("reverse_studio:mapping_rules_editor", project_slug=project_slug)

        if isinstance(payload, dict) and "pipelines" in payload:
            pipelines = payload.get("pipelines") or {}
        elif isinstance(payload, dict):
            pipelines = payload
        else:
            pipelines = {}

    strict = request.POST.get("strict", "") == "1"
    result = transform_rules_persistence_service.save_pipelines(
        request.user,
        project,
        pipelines,
        strict=strict,
    )

    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse(
            "reverse_studio:mapping_rules_editor",
            kwargs={"project_slug": project_slug},
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "mappings": result.payload.get("mappings", []),
                    "warnings": result.payload.get("warning_messages") or [],
                }
            )
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
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


@_rs_view
@require_http_methods(["POST"])
def rules_preview(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto Reverse Studio."},
            status=403,
        )

    sample = request.POST.get("sample", "")
    raw_steps = request.POST.get("pipeline_payload", "").strip()
    steps = []
    if raw_steps:
        try:
            parsed = json.loads(raw_steps)
            steps = parsed if isinstance(parsed, list) else parsed.get("steps") or []
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "message": "JSON de pipeline inválido."},
                status=400,
            )

    use_sample = request.POST.get("from_sample", "") in {"1", "true", "True"}
    target_field = request.POST.get("target_field", "").strip()
    if use_sample:
        result = transform_rules_persistence_service.preview_with_sample_row(
            project,
            target_field=target_field,
            steps=steps,
        )
    else:
        result = transform_rules_persistence_service.preview_value(sample, steps)

    if result.ok:
        return JsonResponse(
            {
                "ok": True,
                "message": result.user_message,
                "input": result.payload.get("input"),
                "output": result.payload.get("output"),
                "from_sample": bool(result.payload.get("from_sample")),
                "target_field": result.payload.get("target_field") or target_field,
            }
        )
    return JsonResponse(
        {
            "ok": False,
            "message": result.user_message,
            "errors": result.errors or {},
        },
        status=400,
    )
