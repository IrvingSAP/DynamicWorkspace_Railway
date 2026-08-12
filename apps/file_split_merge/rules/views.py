from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.source_profile.services import source_persistence_service
from apps.file_split_merge.projects.services import split_merge_project_service
from apps.file_split_merge.rules.services import (
    split_merge_rules_catalog as catalog,
)
from apps.file_split_merge.rules.services import (
    split_merge_rules_persistence_service as rules_svc,
)
from apps.projects.services import project_service

MSG_NO_ACCESS = split_merge_project_service.MSG_NO_ACCESS
FORM_ADD = "file_split_merge:rules:add"


def _sm_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _sidebar() -> dict:
    return {
        "app_nav_active": "file_split_merge",
        "file_split_merge_nav_open": True,
    }


def _get_project(request, project_slug: str):
    project = split_merge_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return None
    return project


def _params_from_post(post, code: str) -> dict:
    if code == "max_rows":
        return {"n": post.get("n", "")}
    if code == "max_bytes":
        return {"bytes": post.get("bytes", "")}
    if code == "split_by_column":
        return {
            "field_name": (post.get("field_name") or "").strip(),
            "include_empty": post.get("include_empty") == "on",
        }
    if code in ("keep_header", "include_header"):
        return {"value": post.get("value") == "on"}
    if code == "missing_columns":
        return {"mode": (post.get("mode") or "error").strip()}
    if code == "dedupe_rows":
        keys = post.getlist("keys") if hasattr(post, "getlist") else []
        if not keys:
            raw = (post.get("keys") or "").strip()
            keys = [k.strip() for k in raw.split(",") if k.strip()]
        return {
            "keys": keys,
            "keep": (post.get("keep") or "first").strip(),
        }
    if code == "append":
        return {}
    return {}


def _posted_from_request(post) -> dict:
    code = (post.get("code") or "").strip()
    return {
        "code": code,
        "enabled": post.get("enabled", "on") == "on",
        "params": _params_from_post(post, code),
    }


def _params_form_values(code: str, params: dict | None) -> dict:
    params = params or {}
    values = {
        "n": params.get("n", ""),
        "bytes": params.get("bytes", ""),
        "field_name": params.get("field_name", ""),
        "include_empty": bool(params.get("include_empty")),
        "value": bool(params.get("value", True)),
        "mode": params.get("mode") or "error",
        "keys": params.get("keys") or [],
        "keep": params.get("keep") or "first",
    }
    return values


@_sm_view
def rules_hub(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    membership = project_service.get_membership(request.user, project)
    hub = rules_svc.get_hub_context(project)
    pending_op = (request.GET.get("pending_operation") or "").strip()
    session_key = f"sm_rules_confirm_op:{project.id}"
    if pending_op not in catalog.OPERATIONS:
        pending_op = ""
        request.session.pop(session_key, None)
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "membership": membership,
            "can_edit": source_persistence_service.user_can_edit_source(
                request.user, project
            ),
            "pending_operation": pending_op,
            **hub,
        }
    )
    return render(request, "file_split_merge/rules/hub.html", ctx)


@_sm_view
def rules_hub_help(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    ctx = _sidebar()
    ctx.update({"project": project})
    return render(request, "file_split_merge/rules/hub_help.html", ctx)


@_sm_view
@require_http_methods(["POST"])
def rules_set_operation(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    operation = (request.POST.get("operation") or "").strip()
    session_key = f"sm_rules_confirm_op:{project.id}"
    pending = (request.session.get(session_key) or "").strip()
    confirm_raw = (request.POST.get("confirm_clear") or "").strip().lower()
    confirm_clear = confirm_raw in ("1", "true", "on", "yes") or (
        bool(pending) and pending == operation
    )
    result = rules_svc.set_operation(
        request.user, project, operation, confirm_clear=confirm_clear
    )
    if result.ok:
        request.session.pop(session_key, None)
        messages.success(request, result.user_message)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)
    if result.error_code == "confirm_required":
        request.session[session_key] = operation
        # Banner en hub (pending_operation); no duplicar el mismo texto en messages.
        url = reverse("file_split_merge:rules_hub", kwargs={"project_slug": project_slug})
        return redirect(f"{url}?pending_operation={operation}")
    request.session.pop(session_key, None)
    messages.error(request, result.user_message)
    return redirect("file_split_merge:rules_hub", project_slug=project_slug)


def _render_form(request, project, *, mode: str, rule_id: str | None, posted, errors):
    hub = rules_svc.get_hub_context(project)
    code = posted.get("code") or (
        hub["catalog_choices"][0]["code"] if hub["catalog_choices"] else ""
    )
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "mode": mode,
            "rule_id": rule_id,
            "posted": {**posted, "code": code},
            "errors": errors,
            "param_values": _params_form_values(code, posted.get("params")),
            "field_names": hub["field_names"],
            "catalog_choices": hub["catalog_choices"],
            "operation": hub["operation"],
            "operation_label": hub["operation_label"],
            "can_edit": True,
        }
    )
    return render(request, "file_split_merge/rules/form.html", ctx)


@_sm_view
@require_http_methods(["GET", "POST"])
def rules_add(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    if not source_persistence_service.user_can_edit_source(request.user, project):
        messages.error(request, rules_svc.MSG_FORBIDDEN)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)

    hub = rules_svc.get_hub_context(project)
    if not hub["profile_complete"]:
        messages.error(request, rules_svc.MSG_PROFILE)
        return redirect("file_split_merge:profile_hub", project_slug=project_slug)
    if not hub["operation"]:
        messages.error(request, rules_svc.MSG_NO_OPERATION)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)

    form_ns = f"{FORM_ADD}:{project_slug}"
    default_code = hub["catalog_choices"][0]["code"] if hub["catalog_choices"] else ""
    posted = {"code": default_code, "enabled": True, "params": {}}
    errors: dict = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", {})
        return _render_form(
            request, project, mode="add", rule_id=None, posted=posted, errors=errors
        )

    posted = _posted_from_request(request.POST)
    result = rules_svc.add_rule(request.user, project, posted)
    if result.ok:
        clear_form_state(request, form_ns)
        messages.success(request, result.user_message)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)
    errors = result.errors or {}
    stash_form_state(request, form_ns, posted, errors)
    messages.error(request, result.user_message)
    return _render_form(
        request, project, mode="add", rule_id=None, posted=posted, errors=errors
    )


@_sm_view
@require_http_methods(["GET", "POST"])
def rules_edit(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    if not source_persistence_service.user_can_edit_source(request.user, project):
        messages.error(request, rules_svc.MSG_FORBIDDEN)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)

    rules = rules_svc.get_rules(project)
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if rule is None:
        messages.error(request, rules_svc.MSG_NOT_FOUND)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)

    form_ns = f"file_split_merge:rules:edit:{project_slug}:{rule_id}"
    posted = {
        "code": rule["code"],
        "enabled": rule.get("enabled", True),
        "params": rule.get("params") or {},
    }
    errors: dict = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", {})
        return _render_form(
            request, project, mode="edit", rule_id=rule_id, posted=posted, errors=errors
        )

    posted = _posted_from_request(request.POST)
    result = rules_svc.update_rule(request.user, project, rule_id, posted)
    if result.ok:
        clear_form_state(request, form_ns)
        messages.success(request, result.user_message)
        return redirect("file_split_merge:rules_hub", project_slug=project_slug)
    errors = result.errors or {}
    stash_form_state(request, form_ns, posted, errors)
    messages.error(request, result.user_message)
    return _render_form(
        request, project, mode="edit", rule_id=rule_id, posted=posted, errors=errors
    )


@_sm_view
@require_http_methods(["POST"])
def rules_toggle(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    result = rules_svc.toggle_rule(request.user, project, rule_id)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_split_merge:rules_hub", project_slug=project_slug)


@_sm_view
@require_http_methods(["POST"])
def rules_delete(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    result = rules_svc.delete_rule(request.user, project, rule_id)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_split_merge:rules_hub", project_slug=project_slug)


@_sm_view
@require_http_methods(["POST"])
def rules_move(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    direction = (request.POST.get("direction") or "").strip()
    result = rules_svc.move_rule(request.user, project, rule_id, direction)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_split_merge:rules_hub", project_slug=project_slug)
