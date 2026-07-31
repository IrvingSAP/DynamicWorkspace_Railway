from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.projects.services import project_service
from apps.structure_scout.apply.services import apply_target_service
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
def apply_hub(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")

    if request.method == "POST":
        action = request.POST.get("action", "apply")
        if action == "apply":
            target_id = (request.POST.get("target_id") or "").strip()
            result = apply_target_service.apply_to_target(
                request.user, project, target_id=target_id
            )
            if result.ok:
                messages.success(request, result.user_message)
                deep_link = (result.payload or {}).get("deep_link")
                target = (result.payload or {}).get("target")
                if deep_link and target is not None:
                    request.session["scout_apply_deep_link"] = deep_link
                    request.session["scout_apply_target_label"] = (
                        f"{target.slug} — {target.name}"
                    )
            else:
                messages.error(request, result.user_message)
            return redirect("structure_scout:apply_hub", project_slug=project_slug)

        # Refresh target list for selected kind (GET-like via POST redirect)
        return redirect(
            "structure_scout:apply_hub",
            project_slug=project_slug,
        )

    ctx_apply = apply_target_service.get_hub_context(request.user, project)
    selected_kind = (
        request.GET.get("kind") or ctx_apply.get("selected_kind") or "file_gate"
    )
    if selected_kind not in {k for k, _ in apply_target_service.MVP_KINDS}:
        selected_kind = "file_gate"
    ctx_apply["selected_kind"] = selected_kind
    if ctx_apply.get("has_draft"):
        ctx_apply["targets"] = apply_target_service.list_eligible_targets(
            request.user, project, selected_kind
        )

    selected_target_id = (request.GET.get("target_id") or "").strip()
    overwrite = None
    if selected_target_id:
        overwrite = apply_target_service.preview_overwrite(
            request.user, project, selected_target_id
        )
    ctx_apply["selected_target_id"] = selected_target_id
    ctx_apply["overwrite"] = overwrite
    ctx_apply["post_apply_deep_link"] = request.session.pop(
        "scout_apply_deep_link", None
    )
    ctx_apply["post_apply_target_label"] = request.session.pop(
        "scout_apply_target_label", None
    )

    hub = scout_project_service.get_hub_context(request.user, project)
    membership = project_service.get_membership(request.user, project)
    ctx = _sidebar()
    ctx.update(ctx_apply)
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "hub": hub,
            "membership": membership,
        }
    )
    return render(request, "structure_scout/apply/hub.html", ctx)


@_ss_view
def apply_hub_help(request, project_slug: str):
    project = scout_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("structure_scout:project_list")
    ctx = _sidebar()
    ctx.update({"project": project, "company": project.company})
    return render(request, "structure_scout/apply/hub_help.html", ctx)
