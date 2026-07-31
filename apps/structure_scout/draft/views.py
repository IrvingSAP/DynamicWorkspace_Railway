from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.projects.services import project_service
from apps.structure_scout.draft.services import save_draft_service
from apps.structure_scout.projects.services import scout_project_service

MSG_NO_ACCESS = "No tiene acceso a este proyecto Explorador."


def _ss_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _sidebar() -> dict:
    return {
        "app_nav_active": "structure_scout",
        "structure_scout_nav_open": True,
    }


@_ss_view
@require_http_methods(["GET", "POST"])
def draft_hub(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "save":
            notes = (request.POST.get("notes") or "").strip()
            result = save_draft_service.save_new_version(
                request.user, project, notes=notes
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
        return redirect("structure_scout:draft_hub", project_slug=project_slug)

    ctx_draft = save_draft_service.get_hub_context(request.user, project)
    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(ctx_draft)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
        }
    )
    return render(request, "structure_scout/draft/hub.html", ctx)


@_ss_view
def draft_hub_help(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")
    ctx = _sidebar()
    ctx.update({"project": project, "company": project.company})
    return render(request, "structure_scout/draft/hub_help.html", ctx)


@_ss_view
@require_GET
def draft_export(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    result = save_draft_service.export_current_json(request.user, project)
    if not result.ok:
        messages.error(request, result.user_message)
        return redirect("structure_scout:draft_hub", project_slug=project_slug)

    return result.payload["response"]
