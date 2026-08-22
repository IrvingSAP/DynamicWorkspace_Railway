from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.catalogs.services.permission_package_service import role_choices_for_ui
from apps.file_pipeline.models import PipelineMembership
from apps.file_pipeline.services import pipeline_dashboard_service as dash_svc
from apps.file_pipeline.services import pipeline_designer_service as designer_svc
from apps.file_pipeline.services import pipeline_history_service as history_svc
from apps.file_pipeline.services import pipeline_project_service as svc
from apps.file_pipeline.services import pipeline_publish_service as publish_svc
from apps.file_pipeline.services import pipeline_run_service as run_svc
from apps.file_pipeline.services import pipeline_step_catalog

FORM_CREATE = "file_pipeline:create"

MSG_NO_ACCESS = svc.MSG_NO_ACCESS
MSG_PA_ONLY = svc.MSG_PA_ONLY


def _sidebar() -> dict:
    return {
        "app_nav_active": "file_pipeline",
        "file_pipeline_nav_open": True,
    }


def _fp_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _pipeline_role_choices() -> list[dict]:
    allowed = PipelineMembership.PIPELINE_ROLES
    items = [item for item in role_choices_for_ui() if item.get("code") in allowed]
    if items:
        return items
    return [
        {"code": code, "label": label, "maps_to_role": code}
        for code, label in PipelineMembership.ROLE_CHOICES
    ]


@_fp_view
def file_pipeline_guide(request):
    profile = request.user.profile
    ctx = _sidebar()
    ctx.update(
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "file_pipeline_guide",
        }
    )
    return render(request, "file_pipeline/guide.html", ctx)


@_fp_view
def pipeline_list(request):
    rows, stats = svc.list_with_stats(request.user)
    ctx = _sidebar()
    ctx.update(
        {
            "rows": rows,
            "stats": stats,
            "company": request.user.profile.company,
        }
    )
    return render(request, "file_pipeline/projects/list.html", ctx)


@_fp_view
def pipeline_list_help(request):
    return render(request, "file_pipeline/projects/list_help.html", _sidebar())


@_fp_view
def pipeline_dashboard(request):
    ctx = _sidebar()
    ctx.update(
        {
            "company": request.user.profile.company,
            "dash": dash_svc.dashboard_context(request.user, request.GET),
            "app_nav_active": "file_pipeline_dashboard",
        }
    )
    return render(request, "file_pipeline/dashboard/home.html", ctx)


@_fp_view
def pipeline_dashboard_help(request):
    ctx = _sidebar()
    ctx.update(
        {
            "company": request.user.profile.company,
            "app_nav_active": "file_pipeline_dashboard",
        }
    )
    return render(request, "file_pipeline/dashboard/home_help.html", ctx)


@_fp_view
def pipeline_create_help(request):
    return render(request, "file_pipeline/projects/create_help.html", _sidebar())


@_fp_view
@require_http_methods(["GET", "POST"])
def pipeline_create(request):
    company = request.user.profile.company
    posted = svc.default_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, FORM_CREATE)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = svc.posted_from_request(request.POST)
        result = svc.create_pipeline(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            pipeline = result.payload["pipeline"]
            return redirect("file_pipeline:pipeline_hub", pipeline_slug=pipeline.slug)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_pipeline:pipeline_create")

    ctx = _sidebar()
    ctx.update({"posted": posted, "errors": errors, "company": company})
    return render(request, "file_pipeline/projects/create.html", ctx)


def _load_or_redirect(request, pipeline_slug: str):
    pipeline = svc.get_pipeline_for_user(request.user, pipeline_slug)
    if pipeline is None:
        messages.error(request, MSG_NO_ACCESS)
        return None, redirect("file_pipeline:pipeline_list")
    return pipeline, None


@_fp_view
@require_http_methods(["GET", "POST"])
def pipeline_hub(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    if request.method == "POST" and request.POST.get("action") == "activate":
        result = svc.set_pipeline_status(
            request.user, pipeline, pipeline.STATUS_ACTIVE
        )
        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return redirect("file_pipeline:pipeline_hub", pipeline_slug=pipeline.slug)
    hub = svc.get_hub_context(request.user, pipeline)
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "hub": hub, "company": pipeline.company})
    return render(request, "file_pipeline/projects/hub.html", ctx)


@_fp_view
def pipeline_hub_help(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company})
    return render(request, "file_pipeline/projects/hub_help.html", ctx)


@_fp_view
@require_http_methods(["GET", "POST"])
def pipeline_members(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    if not svc.user_can_manage_members(request.user, pipeline):
        messages.error(request, MSG_PA_ONLY)
        return redirect("file_pipeline:pipeline_hub", pipeline_slug=pipeline_slug)

    form_ns = f"file_pipeline:members:{pipeline_slug}"
    invite_posted = {"user_id": "", "role": PipelineMembership.ROLE_ED}
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
            result = svc.invite_member(request.user, pipeline, invite_posted)
            if result.ok:
                clear_form_state(request, form_ns)
                messages.success(request, result.user_message)
            else:
                invite_errors = result.errors or {}
                stash_form_state(request, form_ns, invite_posted, invite_errors)
                messages.error(request, result.user_message)
            return redirect("file_pipeline:pipeline_members", pipeline_slug=pipeline_slug)
        if action == "revoke":
            result = svc.set_member_active(
                request.user,
                pipeline,
                request.POST.get("membership_id", ""),
                active=False,
            )
            messages.success(request, result.user_message) if result.ok else messages.error(
                request, result.user_message
            )
            return redirect("file_pipeline:pipeline_members", pipeline_slug=pipeline_slug)
        if action == "reactivate":
            result = svc.set_member_active(
                request.user,
                pipeline,
                request.POST.get("membership_id", ""),
                active=True,
            )
            messages.success(request, result.user_message) if result.ok else messages.error(
                request, result.user_message
            )
            return redirect("file_pipeline:pipeline_members", pipeline_slug=pipeline_slug)
        if action == "change_role":
            result = svc.update_member_role(
                request.user,
                pipeline,
                request.POST.get("membership_id", ""),
                request.POST.get("role", "").strip(),
            )
            messages.success(request, result.user_message) if result.ok else messages.error(
                request, result.user_message
            )
            return redirect("file_pipeline:pipeline_members", pipeline_slug=pipeline_slug)

    hub = svc.get_hub_context(request.user, pipeline)
    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "hub": hub,
            "members": svc.list_members(pipeline),
            "invite_posted": invite_posted,
            "invite_errors": invite_errors,
            "role_choices": _pipeline_role_choices(),
            "company": pipeline.company,
        }
    )
    return render(request, "file_pipeline/projects/members.html", ctx)


@_fp_view
def pipeline_members_help(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    if not svc.user_can_manage_members(request.user, pipeline):
        messages.error(request, MSG_PA_ONLY)
        return redirect("file_pipeline:pipeline_hub", pipeline_slug=pipeline_slug)
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company})
    return render(request, "file_pipeline/projects/members_help.html", ctx)


@_fp_view
@require_http_methods(["GET", "POST"])
def pipeline_designer(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced

    can_edit = designer_svc.user_can_edit_design(request.user, pipeline)
    kinds = pipeline_step_catalog.enabled_kinds(pipeline.company)

    if request.method == "POST":
        if not can_edit:
            messages.error(request, designer_svc.MSG_NO_EDIT)
            return redirect("file_pipeline:pipeline_designer", pipeline_slug=pipeline_slug)
        raw_steps = designer_svc.parse_steps_payload(request.POST)
        if raw_steps is None:
            messages.error(request, designer_svc.MSG_INVALID_STEPS)
            return redirect("file_pipeline:pipeline_designer", pipeline_slug=pipeline_slug)
        result = designer_svc.save_draft(request.user, pipeline, raw_steps)
        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return redirect("file_pipeline:pipeline_designer", pipeline_slug=pipeline_slug)

    first_kind = kinds[0]["kind"] if kinds else ""
    projects = (
        designer_svc.visible_projects_for_kind(request.user, pipeline, first_kind)
        if first_kind
        else []
    )
    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "company": pipeline.company,
            "can_edit": can_edit,
            "kinds": kinds,
            "initial_projects": projects,
            "draft_steps": pipeline.draft_steps or [],
            "design_complete": pipeline.design_complete,
        }
    )
    return render(request, "file_pipeline/designer/designer.html", ctx)


@_fp_view
def pipeline_designer_help(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company})
    return render(request, "file_pipeline/designer/designer_help.html", ctx)


@_fp_view
@require_GET
def pipeline_designer_projects(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return JsonResponse({"results": [], "error": MSG_NO_ACCESS}, status=403)
    kind = request.GET.get("kind", "").strip()
    results = designer_svc.visible_projects_for_kind(request.user, pipeline, kind)
    return JsonResponse({"results": results})


@_fp_view
@require_http_methods(["GET", "POST"])
def pipeline_publish(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    pub = publish_svc.get_publish_context(request.user, pipeline)

    if request.method == "POST":
        if not pipeline.design_complete:
            messages.warning(request, svc.MSG_PUBLISH_BLOCKED)
            return redirect("file_pipeline:pipeline_publish", pipeline_slug=pipeline_slug)
        result = publish_svc.publish_pipeline(request.user, pipeline)
        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return redirect("file_pipeline:pipeline_publish", pipeline_slug=pipeline_slug)

    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "company": pipeline.company,
            "pub": pub,
        }
    )
    return render(request, "file_pipeline/publish/publish.html", ctx)


@_fp_view
def pipeline_publish_help(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company})
    return render(request, "file_pipeline/publish/publish_help.html", ctx)


@_fp_view
@require_http_methods(["GET", "POST"])
def pipeline_run(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    version = pipeline.current_version
    blocked = run_svc.run_gate_reason(pipeline, request.user)
    can_run = blocked == ""
    can_activate = svc.user_can_manage_members(request.user, pipeline)

    if request.method == "POST":
        action = request.POST.get("action", "run")
        if action == "activate":
            result = svc.set_pipeline_status(
                request.user, pipeline, pipeline.STATUS_ACTIVE
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_pipeline:pipeline_run", pipeline_slug=pipeline_slug)
        if blocked:
            messages.warning(request, blocked)
            return redirect("file_pipeline:pipeline_run", pipeline_slug=pipeline_slug)
        result = run_svc.start_run(
            request.user,
            pipeline,
            request.FILES.get("file"),
            dry_run=bool(request.POST.get("dry_run")),
            request=request,
        )
        run = (result.payload or {}).get("run")
        if run is not None:
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect(
                "file_pipeline:pipeline_run_result",
                pipeline_slug=pipeline_slug,
                run_id=run.id,
            )
        messages.error(request, result.user_message)
        return redirect("file_pipeline:pipeline_run", pipeline_slug=pipeline_slug)

    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "company": pipeline.company,
            "version": version,
            "steps": list(version.steps or []) if version else [],
            "blocked": blocked,
            "can_run": can_run,
            "can_activate": can_activate,
            "can_execute": run_svc.user_can_execute_pipeline(request.user, pipeline),
        }
    )
    return render(request, "file_pipeline/run/run.html", ctx)


@_fp_view
def pipeline_run_help(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company})
    return render(request, "file_pipeline/run/run_help.html", ctx)


@_fp_view
def pipeline_run_result(request, pipeline_slug: str, run_id):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    run = run_svc.get_run(pipeline, run_id)
    if run is None:
        messages.error(request, MSG_NO_ACCESS)
        return redirect("file_pipeline:pipeline_run", pipeline_slug=pipeline_slug)
    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "company": pipeline.company,
            "run": run,
            "step_rows": run_svc.step_view_rows(
                run,
                show_job_links=history_svc.user_can_see_job_links(
                    request.user, pipeline
                ),
            ),
        }
    )
    return render(request, "file_pipeline/run/result.html", ctx)


@_fp_view
def pipeline_history(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "company": pipeline.company,
            "history": history_svc.list_context(request.user, pipeline, request.GET),
            "membership": svc.get_membership(request.user, pipeline),
        }
    )
    return render(request, "file_pipeline/history/list.html", ctx)


@_fp_view
@require_http_methods(["POST"])
def pipeline_run_delete(request, pipeline_slug: str, run_id):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    result = history_svc.delete_run(request.user, pipeline, run_id)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_pipeline:pipeline_history", pipeline_slug=pipeline_slug)


@_fp_view
@require_http_methods(["POST"])
def pipeline_history_delete_own(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    result = history_svc.delete_own_runs(request.user, pipeline)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("file_pipeline:pipeline_history", pipeline_slug=pipeline_slug)


@_fp_view
def pipeline_history_help(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company})
    return render(request, "file_pipeline/history/list_help.html", ctx)


@_fp_view
def pipeline_run_audit(request, pipeline_slug: str, run_id):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    run = run_svc.get_run(pipeline, run_id)
    if run is None:
        messages.error(request, history_svc.MSG_NOT_FOUND)
        return redirect("file_pipeline:pipeline_history", pipeline_slug=pipeline_slug)
    ctx = _sidebar()
    ctx.update(
        {
            "pipeline": pipeline,
            "company": pipeline.company,
            "audit": history_svc.audit_context(request.user, pipeline, run),
        }
    )
    return render(request, "file_pipeline/history/detail.html", ctx)


@_fp_view
def pipeline_run_audit_help(request, pipeline_slug: str, run_id):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return bounced
    run = run_svc.get_run(pipeline, run_id)
    if run is None:
        messages.error(request, history_svc.MSG_NOT_FOUND)
        return redirect("file_pipeline:pipeline_history", pipeline_slug=pipeline_slug)
    ctx = _sidebar()
    ctx.update({"pipeline": pipeline, "company": pipeline.company, "run": run})
    return render(request, "file_pipeline/history/detail_help.html", ctx)


@_fp_view
@require_GET
def pipeline_member_search(request, pipeline_slug: str):
    pipeline, bounced = _load_or_redirect(request, pipeline_slug)
    if bounced:
        return JsonResponse({"results": [], "error": MSG_NO_ACCESS}, status=403)
    if not svc.user_can_manage_members(request.user, pipeline):
        return JsonResponse({"results": [], "error": MSG_PA_ONLY}, status=403)
    q = request.GET.get("q", "")
    return JsonResponse({"results": svc.search_invitable(request.user, pipeline, q)})
