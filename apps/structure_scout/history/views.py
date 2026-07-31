from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from apps.core.decorators import security_complete_required, user_type_required
from apps.projects.services import project_service
from apps.structure_scout.draft.services import save_draft_service
from apps.structure_scout.history.services import history_service
from apps.structure_scout.projects.services import scout_project_service

MSG_NO_ACCESS = history_service.MSG_NO_ACCESS


def _ss_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _sidebar() -> dict:
    return {
        "app_nav_active": "structure_scout",
        "structure_scout_nav_open": True,
    }


@_ss_view
@require_GET
def history_hub(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    tipo = (request.GET.get("tipo") or history_service.TIPO_ALL).strip()
    ctx_hist = history_service.get_hub_context(request.user, project, tipo=tipo)
    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(ctx_hist)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
        }
    )
    return render(request, "structure_scout/history/hub.html", ctx)


@_ss_view
@require_GET
def history_hub_help(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")
    ctx = _sidebar()
    ctx.update({"project": project, "company": project.company})
    return render(request, "structure_scout/history/hub_help.html", ctx)


@_ss_view
@require_GET
def history_draft(request, project_slug: str, draft_id):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    detail = history_service.get_draft_detail(request.user, project, draft_id)
    if detail is None:
        messages.error(request, history_service.MSG_DRAFT_NOT_FOUND)
        return redirect("structure_scout:history_hub", project_slug=project_slug)

    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(detail)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
        }
    )
    return render(request, "structure_scout/history/draft_detail.html", ctx)


@_ss_view
@require_GET
def history_draft_export(request, project_slug: str, draft_id):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    detail = history_service.get_draft_detail(request.user, project, draft_id)
    if detail is None:
        messages.error(request, history_service.MSG_DRAFT_NOT_FOUND)
        return redirect("structure_scout:history_hub", project_slug=project_slug)

    result = save_draft_service.export_draft_json(
        request.user, project, detail["draft"]
    )
    if not result.ok:
        messages.error(request, result.user_message)
        return redirect(
            "structure_scout:history_draft",
            project_slug=project_slug,
            draft_id=draft_id,
        )
    return result.payload["response"]


@_ss_view
@require_GET
def history_apply(request, project_slug: str, apply_id):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    detail = history_service.get_apply_detail(request.user, project, apply_id)
    if detail is None:
        messages.error(request, history_service.MSG_APPLY_NOT_FOUND)
        return redirect("structure_scout:history_hub", project_slug=project_slug)

    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(detail)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
        }
    )
    return render(request, "structure_scout/history/apply_detail.html", ctx)
