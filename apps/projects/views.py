from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.catalogs.services.permission_package_service import role_choices_for_ui
from apps.projects.models import ProjectMembership
from apps.projects.services import project_service

FORM_CREATE = "projects:create"


def _form_namespace(action: str, slug=None) -> str:
    if slug:
        return f"projects:{action}:{slug}"
    return f"projects:{action}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _uf_view(view_func):
    return user_type_required("UF")(security_complete_required(view_func))


@_uf_view
def project_list(request):
    rows, stats = project_service.list_with_stats(request.user)
    company = request.user.profile.company
    return render(
        request,
        "projects/project_list.html",
        {
            "rows": rows,
            "stats": stats,
            "company": company,
            "app_nav_active": "projects",
        },
    )


@_uf_view
def project_list_help(request):
    return render(
        request,
        "projects/project_list_help.html",
        {"app_nav_active": "projects"},
    )


@_uf_view
@require_http_methods(["GET", "POST"])
def project_create(request):
    company = request.user.profile.company
    posted = project_service.default_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, FORM_CREATE, posted, errors)

    if request.method == "POST":
        posted = project_service.posted_from_request(request.POST)
        result = project_service.create_project(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            return redirect("projects:detail", slug=result.payload["project"].slug)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("projects:create")

    return render(
        request,
        "projects/project_create.html",
        {
            "posted": posted,
            "errors": errors,
            "company": company,
            "app_nav_active": "projects",
        },
    )


@_uf_view
def project_create_help(request):
    return render(
        request,
        "projects/project_create_help.html",
        {"app_nav_active": "projects"},
    )


@_uf_view
def project_detail(request, slug):
    project = project_service.get_project_for_user(request.user, slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto.")
        return redirect("projects:list")

    membership = project_service.get_membership(request.user, project)
    detail = project_service.get_detail_context(project, membership)
    return render(
        request,
        "projects/project_detail.html",
        {
            "project": project,
            "membership": membership,
            "detail": detail,
            "company": project.company,
            "app_nav_active": "projects",
        },
    )


@_uf_view
def project_detail_help(request, slug):
    project = project_service.get_project_for_user(request.user, slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto.")
        return redirect("projects:list")

    return render(
        request,
        "projects/project_detail_help.html",
        {
            "project": project,
            "company": project.company,
            "app_nav_active": "projects",
        },
    )


@_uf_view
@require_http_methods(["GET", "POST"])
def project_members(request, slug):
    project = project_service.get_project_for_user(request.user, slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto.")
        return redirect("projects:list")

    if not project_service.user_can_manage_members(request.user, project):
        messages.error(request, "Solo el administrador del proyecto (PA) puede gestionar miembros.")
        return redirect("projects:detail", slug=slug)

    form_ns = _form_namespace("members", slug)
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
            return redirect("projects:members", slug=slug)

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
            return redirect("projects:members", slug=slug)

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
            return redirect("projects:members", slug=slug)

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
            return redirect("projects:members", slug=slug)

    members = project_service.list_members(project)
    invitable = project_service.invitable_users(project, request.user)
    actor_membership = project_service.get_membership(request.user, project)

    return render(
        request,
        "projects/project_members.html",
        {
            "project": project,
            "members": members,
            "invitable": invitable,
            "invite_posted": invite_posted,
            "invite_errors": invite_errors,
            "role_choices": role_choices_for_ui(),
            "membership": actor_membership,
            "company": project.company,
            "app_nav_active": "projects",
        },
    )


@_uf_view
def project_members_help(request, slug):
    project = project_service.get_project_for_user(request.user, slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto.")
        return redirect("projects:list")

    if not project_service.user_can_manage_members(request.user, project):
        messages.error(request, "Solo el administrador del proyecto (PA) puede ver la ayuda de miembros.")
        return redirect("projects:detail", slug=slug)

    return render(
        request,
        "projects/project_members_help.html",
        {
            "project": project,
            "company": project.company,
            "app_nav_active": "projects",
        },
    )
