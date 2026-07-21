from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.mapping.services import mapping_project_service
from apps.dms.catalogs.services.permission_package_service import role_choices_for_ui
from apps.projects.services import project_service

FORM_CREATE = "dms:mapping:create"


def _form_namespace(action: str, project_slug=None) -> str:
    if project_slug:
        return f"dms:mapping:{action}:{project_slug}"
    return f"dms:mapping:{action}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _sidebar_context() -> dict:
    return {
        "app_nav_active": "filepipe_mapping",
        "filepipe_nav_open": True,
    }


def _mapping_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


@_mapping_view
def project_list(request):
    rows, stats = mapping_project_service.list_with_stats(request.user)
    company = request.user.profile.company
    ctx = _sidebar_context()
    ctx.update(
        {
            "rows": rows,
            "stats": stats,
            "company": company,
        }
    )
    return render(request, "dms/mapping/list.html", ctx)


@_mapping_view
def project_list_help(request):
    ctx = _sidebar_context()
    return render(request, "dms/mapping/list_help.html", ctx)


@_mapping_view
def project_create_help(request):
    ctx = _sidebar_context()
    return render(request, "dms/mapping/create_help.html", ctx)


@_mapping_view
@require_http_methods(["GET", "POST"])
def project_create(request):
    company = request.user.profile.company
    posted = mapping_project_service.default_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, FORM_CREATE, posted, errors)

    if request.method == "POST":
        posted = mapping_project_service.posted_from_request(request.POST)
        result = mapping_project_service.create_project(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            project = result.payload["project"]
            return redirect("dms:mapping_hub", project_slug=project.slug)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("dms:mapping_create")

    ctx = _sidebar_context()
    ctx.update(
        {
            "posted": posted,
            "errors": errors,
            "company": company,
        }
    )
    return render(request, "dms/mapping/create.html", ctx)


@_mapping_view
def project_hub(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return redirect("dms:mapping_list")

    from django.urls import reverse

    from apps.dms.source_profile.services import (
        source_persistence_service,
        version_publish_service,
    )

    hub = mapping_project_service.get_hub_context(request.user, project)
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
                "dms:source_publish", kwargs={"project_slug": project.slug}
            ),
            "version_publish": version_publish_service.get_publish_context(project),
        }
    )
    return render(request, "dms/mapping/hub.html", ctx)


@_mapping_view
def project_hub_help(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return redirect("dms:mapping_list")

    ctx = _sidebar_context()
    ctx.update({"project": project, "company": project.company})
    return render(request, "dms/mapping/hub_help.html", ctx)


@_mapping_view
@require_http_methods(["GET", "POST"])
def project_members(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return redirect("dms:mapping_list")

    if not project_service.user_can_manage_members(request.user, project):
        messages.error(request, "Solo el administrador del proyecto (PA) puede gestionar miembros.")
        return redirect("dms:mapping_hub", project_slug=project_slug)

    form_ns = _form_namespace("members", project_slug)
    invite_posted = {"user_id": "", "role": ProjectMembership.ROLE_ED}
    invite_errors: dict[str, list[str]] = {}

    if request.method == "GET":
        flashed = take_form_state(request, form_ns)
        if flashed:
            invite_posted = {**invite_posted, **flashed.get("posted", {})}
            invite_errors = flashed.get("errors", {})

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "invite":
            invite_posted = {
                "user_id": request.POST.get("user", "").strip(),
                "role": request.POST.get("role", "").strip(),
            }
            result = project_service.invite_member(request.user, project, invite_posted)
            if result.ok:
                clear_form_state(request, form_ns)
                messages.success(request, result.user_message)
            else:
                invite_errors = result.errors or {}
                stash_form_state(request, form_ns, invite_posted, invite_errors)
                messages.error(request, result.user_message)
            return redirect("dms:mapping_members", project_slug=project_slug)

        if action == "revoke":
            result = project_service.set_member_active(
                request.user,
                project,
                request.POST.get("membership_id", ""),
                active=False,
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("dms:mapping_members", project_slug=project_slug)

        if action == "reactivate":
            result = project_service.set_member_active(
                request.user,
                project,
                request.POST.get("membership_id", ""),
                active=True,
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("dms:mapping_members", project_slug=project_slug)

        if action == "change_role":
            result = project_service.update_member_role(
                request.user,
                project,
                request.POST.get("membership_id", ""),
                request.POST.get("role", "").strip(),
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("dms:mapping_members", project_slug=project_slug)

    members = project_service.list_members(project)
    invitable = project_service.invitable_users(project, request.user)
    actor_membership = project_service.get_membership(request.user, project)
    hub = mapping_project_service.get_hub_context(request.user, project)

    ctx = _sidebar_context()
    ctx.update(
        {
            "project": project,
            "hub": hub,
            "members": members,
            "invitable": invitable,
            "invite_posted": invite_posted,
            "invite_errors": invite_errors,
            "role_choices": role_choices_for_ui(),
            "membership": actor_membership,
            "company": project.company,
        }
    )
    return render(request, "dms/mapping/members.html", ctx)


@_mapping_view
def project_members_help(request, project_slug: str):
    project = mapping_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto DMS.")
        return redirect("dms:mapping_list")

    if not project_service.user_can_manage_members(request.user, project):
        messages.error(request, "Solo el administrador del proyecto (PA) puede gestionar miembros.")
        return redirect("dms:mapping_hub", project_slug=project_slug)

    ctx = _sidebar_context()
    ctx.update({"project": project, "company": project.company})
    return render(request, "dms/mapping/members_help.html", ctx)
