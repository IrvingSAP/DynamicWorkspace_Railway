from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.source_profile.services import source_persistence_service
from apps.file_gate.projects.services import gate_project_service
from apps.file_gate.schema.services import schema_publish_service
from apps.projects.services import project_service

FORM_CREATE = "file_gate:project:create"


def _sidebar_context() -> dict:
    return {
        "app_nav_active": "file_gate",
        "file_gate_nav_open": True,
    }


def _gate_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


@_gate_view
def project_list(request):
    rows, stats = gate_project_service.list_with_stats(request.user)
    company = request.user.profile.company
    ctx = _sidebar_context()
    ctx.update(
        {
            "rows": rows,
            "stats": stats,
            "company": company,
        }
    )
    return render(request, "file_gate/projects/list.html", ctx)


@_gate_view
def project_list_help(request):
    ctx = _sidebar_context()
    return render(request, "file_gate/projects/list_help.html", ctx)


@_gate_view
def project_create_help(request):
    ctx = _sidebar_context()
    return render(request, "file_gate/projects/create_help.html", ctx)


@_gate_view
@require_http_methods(["GET", "POST"])
def project_create(request):
    company = request.user.profile.company
    posted = gate_project_service.default_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, FORM_CREATE)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = gate_project_service.posted_from_request(request.POST)
        result = gate_project_service.create_project(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            project = result.payload["project"]
            return redirect("file_gate:project_hub", project_slug=project.slug)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_gate:project_create")

    ctx = _sidebar_context()
    ctx.update(
        {
            "posted": posted,
            "errors": errors,
            "company": company,
        }
    )
    return render(request, "file_gate/projects/create.html", ctx)


@_gate_view
def project_hub(request, project_slug: str):
    project = gate_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE GATE.")
        return redirect("file_gate:project_list")

    hub = gate_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar_context()
    ctx.update(
        {
            "project": project,
            "hub": hub,
            "membership": membership,
            "company": project.company,
            "can_edit_definition": source_persistence_service.user_can_edit_source(
                request.user, project
            ),
            "source_publish_url": reverse(
                "file_gate:schema_publish", kwargs={"project_slug": project.slug}
            ),
            "version_publish": schema_publish_service.get_publish_context(project),
        }
    )
    return render(request, "file_gate/projects/hub.html", ctx)


@_gate_view
def project_hub_help(request, project_slug: str):
    project = gate_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto FILE GATE.")
        return redirect("file_gate:project_list")

    ctx = _sidebar_context()
    ctx.update({"project": project, "company": project.company})
    return render(request, "file_gate/projects/hub_help.html", ctx)
