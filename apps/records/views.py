from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.projects.services import project_service
from apps.records.models import Record
from apps.records.services import expand_display, record_service


def _form_namespace(action: str, slug: str, pk=None) -> str:
    if pk is not None:
        return f"records:{action}:{slug}:{pk}"
    return f"records:{action}:{slug}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _uf_view(view_func):
    return user_type_required("UF")(security_complete_required(view_func))


def _view_guard(request, slug):
    project, membership = record_service.get_view_context(request.user, slug)
    if project is None:
        messages.error(request, "No tiene acceso a este proyecto.")
        return None, None, redirect("projects:list")
    return project, membership, None


def _edit_guard(request, slug):
    project, membership, redirect_response = _view_guard(request, slug)
    if redirect_response:
        return None, None, redirect_response
    if not record_service.user_can_edit_records(request.user, project):
        messages.error(request, "No tiene permiso para modificar registros en este proyecto.")
        return project, membership, redirect("records:list", slug=slug)
    return project, membership, None


def _list_context(project, membership, *, include_deleted: bool = False, user=None):
    rows, stats, fields, filter_field, filter_choices = record_service.list_with_stats(
        project,
        include_deleted=include_deleted,
    )
    can_edit = record_service.user_can_edit_records(membership.user, project)
    can_configure_display = (
        user is not None and project_service.user_can_manage_members(user, project)
    )
    updated_col_index = len(fields)
    return {
        "project": project,
        "membership": membership,
        "company": project.company,
        "rows": rows,
        "stats": stats,
        "fields": fields,
        "filter_field": filter_field,
        "filter_choices": filter_choices,
        "can_edit": can_edit,
        "can_configure_display": can_configure_display,
        "updated_col_index": updated_col_index,
        "app_nav_active": "projects",
    }


@_uf_view
@require_http_methods(["GET", "POST"])
def record_list(request, slug):
    project, membership, redirect_response = _view_guard(request, slug)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        project, membership, redirect_response = _edit_guard(request, slug)
        if redirect_response:
            return redirect_response
        action = request.POST.get("action", "")
        record_id = request.POST.get("record_id", "")
        if action == "delete":
            result = record_service.soft_delete_record(request.user, project, record_id)
        else:
            messages.error(request, "Acción no válida.")
            return redirect("records:list", slug=slug)
        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return redirect("records:list", slug=slug)

    return render(request, "records/record_list.html", _list_context(project, membership, user=request.user))


@_uf_view
@require_http_methods(["GET"])
def record_expand(request, slug):
    project, membership, redirect_response = _view_guard(request, slug)
    if redirect_response:
        return redirect_response

    context = _list_context(project, membership, user=request.user)
    context["expand_mode"] = True
    context["expand_display"] = expand_display.resolve_expand_theme(project)
    context["can_configure_display"] = project_service.user_can_manage_members(
        request.user,
        project,
    )
    return render(request, "records/record_expand.html", context)


@_uf_view
@require_http_methods(["GET", "POST"])
def record_expand_display(request, slug):
    project, membership, redirect_response = _view_guard(request, slug)
    if redirect_response:
        return redirect_response

    if not project_service.user_can_manage_members(request.user, project):
        messages.error(request, "Solo el administrador del proyecto (PA) puede configurar la apariencia.")
        return redirect("records:expand", slug=slug)

    form_ctx = expand_display.form_context(project)
    posted = form_ctx["posted"]
    errors: dict[str, list[str]] = {}

    if request.method == "POST":
        posted = expand_display.posted_from_request(request.POST)
        result = expand_display.save_expand_theme(project, posted)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("records:expand", slug=slug)
        errors = result.errors or {}
        messages.error(request, result.user_message)
        form_ctx = expand_display.form_context(project, posted_override=posted)

    return render(
        request,
        "records/record_expand_display.html",
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "posted": posted,
            "errors": errors,
            "resolved": form_ctx["resolved"],
            "boolean_fields": form_ctx["boolean_fields"],
            "app_nav_active": "projects",
        },
    )


@_uf_view
@require_http_methods(["GET", "POST"])
def record_create(request, slug):
    project, membership, redirect_response = _edit_guard(request, slug)
    if redirect_response:
        return redirect_response

    fields = list(record_service.active_fields(project))
    form_ns = _form_namespace("create", slug)
    posted = record_service.default_posted(fields)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = record_service.posted_from_request(request.POST, fields)
        result = record_service.create_record(request.user, project, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            record = result.payload["record"]
            return redirect("records:detail", slug=slug, pk=record.pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("records:create", slug=slug)

    return render(
        request,
        "records/record_form.html",
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "fields": fields,
            "form_fields": record_service.form_field_rows(fields, posted, errors),
            "posted": posted,
            "errors": errors,
            "is_edit": False,
            "record": None,
            "can_edit": True,
            "app_nav_active": "projects",
        },
    )


@_uf_view
@require_http_methods(["GET"])
def record_detail(request, slug, pk):
    project, membership, redirect_response = _view_guard(request, slug)
    if redirect_response:
        return redirect_response

    record = record_service.get_record_for_project(project, str(pk))
    if record is None:
        messages.error(request, "Registro no encontrado.")
        return redirect("records:list", slug=slug)

    fields = list(record_service.active_fields(project))
    detail_rows = record_service.get_detail_rows(record, fields)
    can_edit = record_service.user_can_edit_records(request.user, project)
    values_by_field = {fv.field_id: fv for fv in record.field_values.all()}
    detail_label = record_service.record_label(record, fields, values_by_field)

    return render(
        request,
        "records/record_detail.html",
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "record": record,
            "detail_rows": detail_rows,
            "detail_label": detail_label,
            "can_edit": can_edit,
            "app_nav_active": "projects",
        },
    )


@_uf_view
@require_http_methods(["GET", "POST"])
def record_update(request, slug, pk):
    project, membership, redirect_response = _edit_guard(request, slug)
    if redirect_response:
        return redirect_response

    record = get_object_or_404(Record, pk=pk, project=project, is_deleted=False)
    fields = list(record_service.active_fields(project))
    form_ns = _form_namespace("update", slug, pk)
    posted = record_service.posted_from_record(record, fields)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = record_service.posted_from_request(request.POST, fields)
        result = record_service.update_record(request.user, project, record, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("records:detail", slug=slug, pk=record.pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("records:update", slug=slug, pk=pk)

    return render(
        request,
        "records/record_form.html",
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "fields": fields,
            "form_fields": record_service.form_field_rows(fields, posted, errors),
            "posted": posted,
            "errors": errors,
            "is_edit": True,
            "record": record,
            "can_edit": True,
            "app_nav_active": "projects",
        },
    )
