from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.projects.services import project_service
from apps.structure_scout.fields.services import propose_fields_service
from apps.structure_scout.projects.services import scout_project_service

MSG_NO_ACCESS = "No tiene acceso a este proyecto Explorador."
FORM_FIELDS = "structure_scout:fields:confirm"


def _ss_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _sidebar() -> dict:
    return {
        "app_nav_active": "structure_scout",
        "structure_scout_nav_open": True,
    }


def _form_ns(project_slug: str) -> str:
    return f"{FORM_FIELDS}:{project_slug}"


def _annotate_field_errors(fields: list[dict], field_errors: dict) -> list[dict]:
    annotated = []
    for i, item in enumerate(fields):
        row = dict(item)
        row["errors"] = (field_errors or {}).get(str(i), {}) or {}
        annotated.append(row)
    return annotated


@_ss_view
@require_http_methods(["GET", "POST"])
def fields_hub(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    form_ns = _form_ns(project_slug)
    ctx_fields = propose_fields_service.get_hub_context(request.user, project)
    errors: dict = {}

    if request.method == "GET":
        flashed = take_form_state(request, form_ns)
        if flashed:
            posted_fields = flashed.get("posted", {}).get("fields")
            errors = flashed.get("errors", {}) or {}
            field_errors = errors.get("fields") or {}
            if posted_fields is not None:
                ctx_fields["fields"] = _annotate_field_errors(posted_fields, field_errors)
                ctx_fields["field_count"] = len(posted_fields)
            else:
                ctx_fields["fields"] = _annotate_field_errors(
                    ctx_fields.get("fields") or [], field_errors
                )
        else:
            ctx_fields["fields"] = _annotate_field_errors(
                ctx_fields.get("fields") or [], {}
            )

    if request.method == "POST":
        action = request.POST.get("action", "confirm")

        if action == "reinfer":
            result = propose_fields_service.reinfer_fields(request.user, project)
            if result.ok:
                clear_form_state(request, form_ns)
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("structure_scout:fields_hub", project_slug=project_slug)

        fields = propose_fields_service.fields_from_request(request.POST)
        result = propose_fields_service.confirm_fields(request.user, project, fields)
        if result.ok:
            clear_form_state(request, form_ns)
            if "revisión pendiente" in (result.user_message or "").lower():
                messages.warning(request, result.user_message)
            else:
                messages.success(request, result.user_message)
            return redirect("structure_scout:fields_hub", project_slug=project_slug)

        errors = result.errors or {}
        stash_form_state(request, form_ns, {"fields": fields}, errors)
        messages.error(request, result.user_message)
        return redirect("structure_scout:fields_hub", project_slug=project_slug)

    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(ctx_fields)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
            "errors": errors,
        }
    )
    return render(request, "structure_scout/fields/hub.html", ctx)


@_ss_view
def fields_hub_help(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")
    ctx = _sidebar()
    ctx.update({"project": project, "company": project.company})
    return render(request, "structure_scout/fields/hub_help.html", ctx)
