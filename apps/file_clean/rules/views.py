from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.source_profile.services import source_persistence_service
from apps.file_clean.projects.services import clean_project_service
from apps.file_clean.rules.services import clean_rules_persistence_service as rules_svc
from apps.projects.services import project_service

MSG_NO_ACCESS = clean_project_service.MSG_NO_ACCESS
FORM_ADD = "file_clean:rules:add"


def _fc_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _sidebar() -> dict:
    return {"app_nav_active": "file_clean", "file_clean_nav_open": True}


def _get_project(request, project_slug: str):
    project = clean_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return None
    return project


def _params_from_post(post, code: str) -> dict:
    params: dict = {}
    if code == "null_tokens":
        params["tokens"] = post.get("tokens", "N/A,null,—")
    elif code == "date_normalize":
        params["input_formats"] = post.get("input_formats", "")
        params["output_format"] = post.get("output_format", "%Y-%m-%d")
    elif code == "number_normalize":
        params["decimal_sep"] = post.get("decimal_sep", ".")
        params["thousands_sep"] = post.get("thousands_sep", ",")
    elif code == "replace_map":
        params["map"] = post.get("map_text", "")
        params["case_insensitive"] = post.get("case_insensitive") == "on"
    elif code == "replace":
        params["find"] = post.get("find", "")
        params["replace"] = post.get("replace", "")
        params["all"] = post.get("all", "on") == "on"
        params["ignore_case"] = post.get("ignore_case") == "on"
        params["regex"] = post.get("regex") == "on"
    elif code == "compose":
        params["template"] = post.get("template", "")
        params["seq_start"] = post.get("seq_start", "1")
        params["seq_step"] = post.get("seq_step", "1")
        params["seq_width"] = post.get("seq_width", "")
        params["seq_pad_char"] = post.get("seq_pad_char", "0")
    elif code == "dedupe_rows":
        params["key_fields"] = post.get("key_fields", "")
    elif code == "encoding_normalize":
        params["target_encoding"] = post.get("target_encoding", "utf-8")
        params["strip_bom"] = post.get("strip_bom", "on") == "on"
    return params


def _posted_from_request(post) -> dict:
    code = (post.get("code") or "").strip()
    return {
        "code": code,
        "field_name": (post.get("field_name") or "").strip(),
        "enabled": post.get("enabled", "on") == "on",
        "params": _params_from_post(post, code),
    }


def _params_form_values(code: str, params: dict | None) -> dict:
    params = params or {}
    values = {
        "tokens": "N/A,null,—",
        "input_formats": "",
        "output_format": "%Y-%m-%d",
        "decimal_sep": ".",
        "thousands_sep": ",",
        "map_text": "",
        "case_insensitive": False,
        "find": "",
        "replace": "",
        "all": True,
        "ignore_case": False,
        "template": "",
        "seq_start": 1,
        "seq_step": 1,
        "seq_width": "",
        "seq_pad_char": "0",
        "key_fields": "",
        "target_encoding": "utf-8",
        "strip_bom": True,
    }
    if code == "null_tokens":
        tokens = params.get("tokens") or ["N/A", "null", "—", ""]
        values["tokens"] = ",".join(str(t) for t in tokens)
    elif code == "date_normalize":
        values["input_formats"] = ",".join(params.get("input_formats") or [])
        values["output_format"] = params.get("output_format") or "%Y-%m-%d"
    elif code == "number_normalize":
        values["decimal_sep"] = params.get("decimal_sep") or "."
        values["thousands_sep"] = params.get("thousands_sep") or ","
    elif code == "replace_map":
        mapping = params.get("map") or {}
        values["map_text"] = "\n".join(f"{k}={v}" for k, v in mapping.items())
        values["case_insensitive"] = bool(params.get("case_insensitive"))
    elif code == "replace":
        values["find"] = params.get("find", "")
        values["replace"] = params.get("replace", "")
        values["all"] = bool(params.get("all", True))
        values["ignore_case"] = bool(params.get("ignore_case"))
    elif code == "compose":
        values["template"] = params.get("template", "")
        values["seq_start"] = params.get("seq_start", 1)
        values["seq_step"] = params.get("seq_step", 1)
        values["seq_width"] = params.get("seq_width", "") or ""
        values["seq_pad_char"] = params.get("seq_pad_char", "0")
    elif code == "dedupe_rows":
        values["key_fields"] = ",".join(params.get("key_fields") or [])
    elif code == "encoding_normalize":
        values["target_encoding"] = params.get("target_encoding") or "utf-8"
        values["strip_bom"] = bool(params.get("strip_bom", True))
    return values


@_fc_view
def rules_hub(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")

    membership = project_service.get_membership(request.user, project)
    hub = rules_svc.get_hub_context(project)
    orphans = rules_svc.orphaned_field_refs(project)
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "membership": membership,
            "company": project.company,
            "can_edit": source_persistence_service.user_can_edit_source(
                request.user, project
            ),
            "orphan_rule_ids": orphans,
            **hub,
        }
    )
    return render(request, "file_clean/rules/hub.html", ctx)


@_fc_view
def rules_hub_help(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    ctx = _sidebar()
    ctx.update({"project": project, "company": project.company})
    return render(request, "file_clean/rules/hub_help.html", ctx)


@_fc_view
@require_http_methods(["GET", "POST"])
def rules_add(request, project_slug: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    if not source_persistence_service.user_can_edit_source(request.user, project):
        messages.error(request, rules_svc.MSG_FORBIDDEN)
        return redirect("file_clean:rules_hub", project_slug=project_slug)

    form_ns = f"{FORM_ADD}:{project_slug}"
    posted = {
        "code": "trim",
        "field_name": "",
        "enabled": True,
        "params": {},
    }
    errors: dict = {}
    hub = rules_svc.get_hub_context(project)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", {})

    if request.method == "POST":
        posted = _posted_from_request(request.POST)
        result = rules_svc.add_rule(request.user, project, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_clean:rules_hub", project_slug=project_slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_clean:rules_add", project_slug=project_slug)

    params_values = _params_form_values(posted.get("code") or "trim", posted.get("params"))
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "posted": posted,
            "errors": errors,
            "params_values": params_values,
            "catalog_choices": hub["catalog_choices"],
            "field_names": hub["field_names"],
            "mode": "add",
            "can_edit": True,
        }
    )
    return render(request, "file_clean/rules/form.html", ctx)


@_fc_view
@require_http_methods(["GET", "POST"])
def rules_edit(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    if not source_persistence_service.user_can_edit_source(request.user, project):
        messages.error(request, rules_svc.MSG_FORBIDDEN)
        return redirect("file_clean:rules_hub", project_slug=project_slug)

    rules = rules_svc.get_rules(project)
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if rule is None:
        messages.error(request, rules_svc.MSG_NOT_FOUND)
        return redirect("file_clean:rules_hub", project_slug=project_slug)

    form_ns = f"file_clean:rules:edit:{project_slug}:{rule_id}"
    posted = {
        "code": rule["code"],
        "field_name": rule.get("field_name") or "",
        "enabled": rule.get("enabled", True),
        "params": rule.get("params") or {},
    }
    errors: dict = {}
    hub = rules_svc.get_hub_context(project)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", {})

    if request.method == "POST":
        posted = _posted_from_request(request.POST)
        result = rules_svc.update_rule(request.user, project, rule_id, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_clean:rules_hub", project_slug=project_slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_clean:rules_edit", project_slug=project_slug, rule_id=rule_id)

    params_values = _params_form_values(posted.get("code") or rule["code"], posted.get("params"))
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "company": project.company,
            "posted": posted,
            "errors": errors,
            "params_values": params_values,
            "catalog_choices": hub["catalog_choices"],
            "field_names": hub["field_names"],
            "mode": "edit",
            "rule_id": rule_id,
            "can_edit": True,
        }
    )
    return render(request, "file_clean/rules/form.html", ctx)


@_fc_view
@require_http_methods(["POST"])
def rules_toggle(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    result = rules_svc.toggle_rule(request.user, project, rule_id)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_clean:rules_hub", project_slug=project_slug)


@_fc_view
@require_http_methods(["POST"])
def rules_delete(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    result = rules_svc.delete_rule(request.user, project, rule_id)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_clean:rules_hub", project_slug=project_slug)


@_fc_view
@require_http_methods(["POST"])
def rules_move(request, project_slug: str, rule_id: str):
    project = _get_project(request, project_slug)
    if project is None:
        return redirect("file_clean:project_list")
    direction = (request.POST.get("direction") or "").strip()
    result = rules_svc.move_rule(request.user, project, rule_id, direction)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_clean:rules_hub", project_slug=project_slug)
