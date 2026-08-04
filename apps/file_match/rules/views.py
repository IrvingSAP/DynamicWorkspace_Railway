import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.projects.services import match_project_service
from apps.file_match.rules.services import (
    match_rules_persistence_service,
    match_rules_wizard_service,
)
from apps.projects.services import project_service


def _rules_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = match_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE MATCH.")
        return None
    return project


def _base_context(request, project, current_section: str | None = None) -> dict:
    membership = project_service.get_membership(request.user, project)
    wizard = match_rules_wizard_service.get_rules_context(project, membership)
    return {
        "project": project,
        "wizard": wizard,
        "membership": membership,
        "current_section": current_section,
        "app_nav_active": "file_match",
        "file_match_nav_open": True,
        "can_edit_source": source_persistence_service.user_can_edit_source(
            request.user, project
        ),
        "rules_save_url": reverse(
            "file_match:rules_save", kwargs={"project_slug": project.slug}
        ),
        "rules": wizard.rules,
        "rules_json": wizard.rules_json,
        "fields_a": wizard.fields_a,
        "fields_b": wizard.fields_b,
    }


@_rules_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/hub.html",
        _base_context(request, project),
    )


@_rules_view
@require_http_methods(["POST"])
def suggest_homonyms(request, project_slug: str):
    from apps.file_match.profile_b.services import copy_from_a_service

    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    if not source_persistence_service.user_can_edit_source(request.user, project):
        messages.error(request, "No tiene permiso para editar el contrato de este proyecto.")
        return redirect("file_match:rules_hub", project_slug=project_slug)

    rules = match_rules_persistence_service.get_rules_dict(project)
    if rules.get("key"):
        messages.error(
            request,
            "Ya hay clave definida. Borre o edite los pares existentes antes de proponer 1:1.",
        )
        return redirect("file_match:rules_hub", project_slug=project_slug)

    partial = copy_from_a_service.build_homonym_rules_partial(project)
    if not partial:
        messages.error(
            request,
            "No hay campos con el mismo nombre en A y B para proponer pares 1:1.",
        )
        return redirect("file_match:rules_hub", project_slug=project_slug)

    result = match_rules_persistence_service.save_rules(
        request.user, project, partial, strict=False
    )
    if result.ok:
        messages.success(
            request,
            "Se propusieron pares 1:1 por nombre (primer campo como clave). Revise y ajuste.",
        )
    else:
        messages.error(request, result.user_message or "No se pudieron proponer las reglas.")
    return redirect("file_match:rules_hub", project_slug=project_slug)


@_rules_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/hub_help.html",
        _base_context(request, project),
    )


@_rules_view
def keys_edit(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/keys.html",
        _base_context(request, project, current_section="keys"),
    )


@_rules_view
def keys_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/keys_help.html",
        _base_context(request, project, current_section="keys"),
    )


@_rules_view
def compare_edit(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/compare.html",
        _base_context(request, project, current_section="compare"),
    )


@_rules_view
def compare_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/compare_help.html",
        _base_context(request, project, current_section="compare"),
    )


@_rules_view
def normalize_edit(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/normalize.html",
        _base_context(request, project, current_section="normalize"),
    )


@_rules_view
def normalize_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_match:project_list")
    return render(
        request,
        "file_match/rules/normalize_help.html",
        _base_context(request, project, current_section="normalize"),
    )


@_rules_view
@require_http_methods(["POST"])
def rules_save(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "No tiene acceso a este proyecto FILE MATCH."},
                status=403,
            )
        return redirect("file_match:project_list")

    payload: dict = {}
    raw = request.POST.get("rules_payload", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "JSON de reglas de cruce inválido."},
                    status=400,
                )
            messages.error(request, "JSON de reglas de cruce inválido.")
            return redirect("file_match:rules_hub", project_slug=project_slug)
    else:
        # Form fields: key_a[], key_b[], compare_a[], compare_b[], normalize flags
        key_a = request.POST.getlist("key_a")
        key_b = request.POST.getlist("key_b")
        if key_a or key_b:
            payload["key"] = [
                {"a": (a or "").strip(), "b": (b or "").strip()}
                for a, b in zip(key_a, key_b)
            ]
        compare_a = request.POST.getlist("compare_a")
        compare_b = request.POST.getlist("compare_b")
        if "compare_a" in request.POST or "compare_b" in request.POST:
            payload["compare"] = [
                {"a": (a or "").strip(), "b": (b or "").strip()}
                for a, b in zip(compare_a, compare_b)
            ]
        if "normalize_present" in request.POST:
            payload["normalize"] = {
                "trim": request.POST.get("trim") == "1",
                "case_fold_keys": request.POST.get("case_fold_keys") == "1",
            }
        if "on_duplicate_key" in request.POST:
            payload["on_duplicate_key"] = request.POST.get("on_duplicate_key", "").strip()

    strict = request.POST.get("strict", "") == "1"
    result = match_rules_persistence_service.save_rules(
        request.user,
        project,
        payload,
        strict=strict,
    )

    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse("file_match:rules_hub", kwargs={"project_slug": project_slug})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "rules": result.payload.get("rules", {}),
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
