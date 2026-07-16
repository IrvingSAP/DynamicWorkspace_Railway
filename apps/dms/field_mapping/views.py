from django.contrib import messages
import json

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
from apps.dms.mapping.services import mapping_project_service
from apps.dms.source_profile.services import version_publish_service
from apps.projects.services import project_service


def _mapping_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return None
    return project


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    editor = field_mapping_service.get_editor_context(project, membership)
    return {
        "project": project,
        "membership": membership,
        "app_nav_active": "filepipe_mapping",
        "filepipe_nav_open": True,
        "can_edit_mappings": field_mapping_persistence_service.user_can_edit_mappings(
            request.user, project
        ),
        "mapping_save_url": reverse("dms:field_mapping_save", kwargs={"project_slug": project.slug}),
        "mapping_preview_url": reverse(
            "dms:field_mapping_preview", kwargs={"project_slug": project.slug}
        ),
        "version_publish": version_publish_service.get_publish_context(project),
        **editor,
    }


@_mapping_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project)
    return render(request, "dms/field_mapping/hub.html", ctx)


@_mapping_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project)
    return render(request, "dms/field_mapping/hub_help.html", ctx)


@_mapping_view
def editor(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project)
    if not ctx["source_fields"] or not ctx["target_fields"]:
        messages.warning(
            request,
            "Complete primero la definición de origen y destino antes de mapear campos.",
        )
        if not ctx["source_fields"]:
            return redirect("dms:source_hub", project_slug=project_slug)
        return redirect("dms:target_hub", project_slug=project_slug)
    return render(request, "dms/field_mapping/editor.html", ctx)


@_mapping_view
def editor_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("dms:mapping_list")
    ctx = _base_context(request, project)
    return render(request, "dms/field_mapping/editor_help.html", ctx)


@_mapping_view
@require_http_methods(["POST"])
def mapping_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
                status=403,
            )
        return redirect("dms:mapping_list")

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
            return redirect("dms:field_mapping_editor", project_slug=project_slug)

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
        redirect_to = reverse("dms:field_mapping_editor", kwargs={"project_slug": project_slug})

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


@_mapping_view
@require_http_methods(["POST"])
def mapping_preview(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return JsonResponse(
            {"ok": False, "message": "No tiene acceso a este proyecto DMS."},
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
                {"ok": False, "message": "JSON de fila origen inválido."},
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
