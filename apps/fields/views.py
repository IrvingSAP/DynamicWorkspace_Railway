from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.fields.models import FieldDefinition
from apps.fields.services import field_service


def _form_namespace(action: str, slug: str, pk=None) -> str:
    if pk is not None:
        return f"fields:{action}:{slug}:{pk}"
    return f"fields:{action}:{slug}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _uf_view(view_func):
    return user_type_required("UF")(security_complete_required(view_func))


def _design_guard(request, slug):
    project, membership = field_service.get_design_context(request.user, slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto.")
        return None, None, redirect("projects:list")
    if membership is None:
        messages.error(request, "Solo el administrador del proyecto (PA) puede diseñar campos.")
        return project, None, redirect("projects:detail", slug=slug)
    return project, membership, None


@_uf_view
@require_http_methods(["GET", "POST"])
def field_list(request, slug):
    project, membership, redirect_response = _design_guard(request, slug)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        action = request.POST.get("action", "")
        field_id = request.POST.get("field_id", "")
        if action == "deactivate":
            result = field_service.set_field_active(
                request.user, project, field_id, active=False,
            )
        elif action == "reactivate":
            result = field_service.set_field_active(
                request.user, project, field_id, active=True,
            )
        else:
            messages.error(request, "Acción no válida.")
            return redirect("fields:list", slug=slug)

        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return redirect("fields:list", slug=slug)

    rows, stats = field_service.list_with_stats(project)
    return render(
        request,
        "fields/field_list.html",
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "rows": rows,
            "stats": stats,
            "field_type_choices": FieldDefinition.FIELD_TYPE_CHOICES,
            "app_nav_active": "projects",
        },
    )


@_uf_view
@require_http_methods(["GET", "POST"])
def field_create(request, slug):
    project, membership, redirect_response = _design_guard(request, slug)
    if redirect_response:
        return redirect_response

    form_ns = _form_namespace("create", slug)
    posted = field_service.default_posted(project=project)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = field_service.posted_from_request(request.POST)
        result = field_service.create_field(request.user, project, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("fields:list", slug=slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("fields:create", slug=slug)

    return render(
        request,
        "fields/field_create.html",
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "posted": posted,
            "errors": errors,
            "field_type_choices": FieldDefinition.FIELD_TYPE_CHOICES,
            "key_readonly": False,
            "is_edit": False,
            "app_nav_active": "projects",
        },
    )


@_uf_view
@require_http_methods(["GET", "POST"])
def field_update(request, slug, pk):
    project, membership, redirect_response = _design_guard(request, slug)
    if redirect_response:
        return redirect_response

    field = get_object_or_404(FieldDefinition, pk=pk, project=project)
    form_ns = _form_namespace("update", slug, pk)
    posted = field_service.default_posted(field)
    errors: dict[str, list[str]] = {}
    key_readonly = field_service.field_has_values(field)

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = field_service.posted_from_request(request.POST)
        result = field_service.update_field(request.user, project, field, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("fields:list", slug=slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("fields:update", slug=slug, pk=pk)

    return render(
        request,
        "fields/field_update.html",
        {
            "project": project,
            "field": field,
            "membership": membership,
            "company": project.company,
            "posted": posted,
            "errors": errors,
            "field_type_choices": FieldDefinition.FIELD_TYPE_CHOICES,
            "key_readonly": key_readonly,
            "is_edit": True,
            "app_nav_active": "projects",
        },
    )
