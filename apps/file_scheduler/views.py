from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.catalogs.services.permission_package_service import role_choices_for_ui
from apps.file_scheduler.models import Schedule, ScheduleMembership
from apps.file_scheduler.services import schedule_audit as audit_svc
from apps.file_scheduler.services import schedule_cron as cron_svc
from apps.file_scheduler.services import schedule_dependency as dep_svc
from apps.file_scheduler.services import schedule_errors as err
from apps.file_scheduler.services import schedule_integration as integ_svc
from apps.file_scheduler.services import schedule_lifecycle_service as svc
from apps.file_scheduler.services import schedule_notify as notify_svc
from apps.file_scheduler.services import schedule_target as target_svc
from apps.file_scheduler.services import schedule_tick as tick_svc

FORM_CREATE = "file_scheduler:create"

MSG_NO_ACCESS = svc.MSG_NO_ACCESS
MSG_PA_ONLY = svc.MSG_PA_ONLY


def _sidebar() -> dict:
    return {
        "app_nav_active": "file_scheduler",
        "file_scheduler_nav_open": True,
    }


def _sch_view(view_func):
    return security_complete_required(user_type_required("US", "UF")(view_func))


def _schedule_role_choices() -> list[dict]:
    allowed = ScheduleMembership.SCHEDULE_ROLES
    items = [item for item in role_choices_for_ui() if item.get("code") in allowed]
    if items:
        return items
    return [
        {"code": code, "label": label, "maps_to_role": code}
        for code, label in ScheduleMembership.ROLE_CHOICES
    ]


@_sch_view
def schedule_guide(request):
    profile = request.user.profile
    ctx = _sidebar()
    ctx.update(
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "file_scheduler_guide",
            "can_create": svc.user_can_create(request.user),
        }
    )
    return render(request, "file_scheduler/guide.html", ctx)


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_list(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        slug = (request.POST.get("schedule_slug") or "").strip()
        schedule = svc.get_schedule_for_user(request.user, slug) if slug else None
        if schedule is None:
            raise Http404()
        result = None
        if action == "archive":
            result = svc.archive_schedule(request.user, schedule)
        elif action == "pause":
            result = svc.pause_schedule(request.user, schedule)
        elif action == "resume":
            result = svc.resume_schedule(request.user, schedule)
        if result is not None:
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_list")
    rows, stats = svc.list_with_stats(request.user)
    ctx = _sidebar()
    ctx.update(
        {
            "rows": rows,
            "stats": stats,
            "company": request.user.profile.company,
            "can_create": svc.user_can_create(request.user),
        }
    )
    return render(request, "file_scheduler/projects/list.html", ctx)


@_sch_view
def schedule_list_help(request):
    ctx = _sidebar()
    ctx.update({"can_create": svc.user_can_create(request.user)})
    return render(request, "file_scheduler/projects/list_help.html", ctx)


@_sch_view
def schedule_errors_help(request):
    ctx = _sidebar()
    ctx.update({"company": request.user.profile.company})
    return render(request, "file_scheduler/errors/errors_help.html", ctx)


@_sch_view
def schedule_errors(request):
    ctx = _sidebar()
    ctx.update(
        {
            "company": request.user.profile.company,
            "rows": err.catalog_rows(),
        }
    )
    return render(request, "file_scheduler/errors/errors.html", ctx)


@_sch_view
def schedule_integration_help(request):
    ctx = _sidebar()
    ctx.update({"company": request.user.profile.company})
    return render(request, "file_scheduler/integration/integration_help.html", ctx)


@_sch_view
def schedule_integration(request):
    ctx = _sidebar()
    ctx.update(
        {
            "company": request.user.profile.company,
            "integ": integ_svc.map_context(),
        }
    )
    return render(request, "file_scheduler/integration/integration.html", ctx)


@_sch_view
def schedule_create_help(request):
    if not svc.user_can_create(request.user):
        messages.error(request, svc.MSG_CREATE_FORBIDDEN)
        return redirect("file_scheduler:schedule_list")
    return render(request, "file_scheduler/projects/create_help.html", _sidebar())


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_create(request):
    if not svc.user_can_create(request.user):
        messages.error(request, svc.MSG_CREATE_FORBIDDEN)
        return redirect("file_scheduler:schedule_list")

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
        result = svc.create_schedule(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            schedule = result.payload["schedule"]
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_create")

    ctx = _sidebar()
    ctx.update({"posted": posted, "errors": errors, "company": company})
    return render(request, "file_scheduler/projects/create.html", ctx)


def _load_or_redirect(request, schedule_slug: str):
    schedule = svc.get_schedule_for_user(request.user, schedule_slug)
    if schedule is None:
        raise Http404()
    return schedule, None


def _raise_if_opaque(result):
    if result is not None and result.error_code in err.OPAQUE_CODES:
        raise Http404()


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_hub(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "pause":
            result = svc.pause_schedule(request.user, schedule)
        elif action == "resume":
            result = svc.resume_schedule(request.user, schedule)
        elif action == "activate":
            result = svc.activate_schedule(request.user, schedule)
        elif action == "archive":
            result = svc.archive_schedule(request.user, schedule)
        else:
            result = None
        if result is not None:
            if result.ok:
                messages.success(request, result.user_message)
                if action == "archive":
                    return redirect("file_scheduler:schedule_list")
            else:
                messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "hub": hub, "company": schedule.company})
    return render(request, "file_scheduler/projects/hub.html", ctx)


@_sch_view
def schedule_hub_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/projects/hub_help.html", ctx)


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_edit(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    if not svc.user_can_edit(request.user, schedule):
        messages.error(request, svc.MSG_FORBIDDEN)
        return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)

    form_ns = f"file_scheduler:edit:{schedule_slug}"
    posted = {
        "name": schedule.name,
        "slug": schedule.slug,
        "description": schedule.description,
        "visibility": schedule.visibility,
    }
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = svc.posted_from_request(request.POST)
        posted["slug"] = schedule.slug
        result = svc.update_schedule(request.user, schedule, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_edit", schedule_slug=schedule.slug)

    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "posted": posted,
            "errors": errors,
            "company": schedule.company,
        }
    )
    return render(request, "file_scheduler/projects/edit.html", ctx)


@_sch_view
def schedule_edit_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/projects/edit_help.html", ctx)


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_members(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    if not svc.user_can_manage_members(request.user, schedule):
        messages.error(request, MSG_PA_ONLY)
        return redirect("file_scheduler:schedule_hub", schedule_slug=schedule_slug)

    form_ns = f"file_scheduler:members:{schedule_slug}"
    invite_posted = {"user_id": "", "role": ScheduleMembership.ROLE_ED}
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
            result = svc.invite_member(request.user, schedule, invite_posted)
            if result.ok:
                clear_form_state(request, form_ns)
                messages.success(request, result.user_message)
            else:
                invite_errors = result.errors or {}
                stash_form_state(request, form_ns, invite_posted, invite_errors)
                messages.error(request, result.user_message)
            return redirect("file_scheduler:schedule_members", schedule_slug=schedule_slug)
        if action == "revoke":
            result = svc.set_member_active(
                request.user,
                schedule,
                request.POST.get("membership_id", ""),
                active=False,
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_scheduler:schedule_members", schedule_slug=schedule_slug)
        if action == "reactivate":
            result = svc.set_member_active(
                request.user,
                schedule,
                request.POST.get("membership_id", ""),
                active=True,
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_scheduler:schedule_members", schedule_slug=schedule_slug)
        if action == "change_role":
            result = svc.update_member_role(
                request.user,
                schedule,
                request.POST.get("membership_id", ""),
                request.POST.get("role", "").strip(),
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_scheduler:schedule_members", schedule_slug=schedule_slug)

    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "hub": hub,
            "members": svc.list_members(schedule),
            "invite_posted": invite_posted,
            "invite_errors": invite_errors,
            "role_choices": _schedule_role_choices(),
            "company": schedule.company,
        }
    )
    return render(request, "file_scheduler/projects/members.html", ctx)


@_sch_view
def schedule_members_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    if not svc.user_can_manage_members(request.user, schedule):
        messages.error(request, MSG_PA_ONLY)
        return redirect("file_scheduler:schedule_hub", schedule_slug=schedule_slug)
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/projects/members_help.html", ctx)


@_sch_view
@require_GET
def schedule_member_search(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return JsonResponse({"results": [], "error": MSG_NO_ACCESS}, status=403)
    if not svc.user_can_manage_members(request.user, schedule):
        return JsonResponse({"results": [], "error": MSG_PA_ONLY}, status=403)
    results = svc.search_invitable(request.user, schedule, request.GET.get("q", ""))
    return JsonResponse({"results": results})


@_sch_view
def schedule_audit(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    events = svc.list_audit_events(schedule)
    rows = audit_svc.list_audit_rows(schedule)
    stats = {
        "total": len(rows),
        "definition": sum(1 for r in rows if r["plane"] == audit_svc.PLANE_DEFINITION),
        "tick": sum(1 for r in rows if r["plane"] == audit_svc.PLANE_TICK),
    }
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "events": events,
            "rows": rows,
            "stats": stats,
            "company": schedule.company,
            "hub": svc.get_hub_context(request.user, schedule),
        }
    )
    return render(request, "file_scheduler/audit/audit.html", ctx)


@_sch_view
def schedule_audit_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/audit/audit_help.html", ctx)


@_sch_view
def schedule_cron_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/cron/cron_help.html", ctx)


@_sch_view
@require_GET
def schedule_cron_preview(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return JsonResponse({"ok": False, "slots": [], "error": MSG_NO_ACCESS}, status=403)
    data = svc.programming_posted_from_request(request.GET)
    result = cron_svc.preview_slots(data)
    return JsonResponse(
        {
            "ok": result["ok"],
            "slots": result.get("slots") or [],
            "error": result.get("user_message") or "",
        }
    )


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_cron(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    form_ns = f"file_scheduler:cron:{schedule_slug}"
    posted = cron_svc.snapshot_from_schedule(schedule)
    errors: dict[str, list[str]] = {}
    can_edit = svc.user_can_edit(request.user, schedule)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = svc.programming_posted_from_request(request.POST)
        result = svc.save_programming(request.user, schedule, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_cron", schedule_slug=schedule.slug)

    tz_list = list(cron_svc.COMMON_TIMEZONES)
    tz_val = posted.get("timezone") or cron_svc.DEFAULT_TIMEZONE
    if tz_val not in tz_list:
        tz_list = [tz_val] + tz_list
    preview = cron_svc.preview_slots(posted)
    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "posted": posted,
            "errors": errors,
            "company": schedule.company,
            "can_edit": can_edit,
            "hub": hub,
            "preview_slots": preview.get("slots") or [],
            "timezones": tz_list,
            "preview_url": reverse(
                "file_scheduler:schedule_cron_preview",
                kwargs={"schedule_slug": schedule.slug},
            ),
        }
    )
    return render(request, "file_scheduler/cron/cron.html", ctx)


@_sch_view
def schedule_target_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/target/target_help.html", ctx)


@_sch_view
@require_GET
def schedule_target_projects(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return JsonResponse({"ok": False, "projects": []}, status=403)
    kind = (request.GET.get("kind") or "").strip()
    rows = target_svc.list_projects_for_kind(schedule.company, kind)
    return JsonResponse({"ok": True, "projects": rows})


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_target(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    form_ns = f"file_scheduler:target:{schedule_slug}"
    posted = target_svc.snapshot_from_schedule(schedule)
    errors: dict[str, list[str]] = {}
    can_edit = svc.user_can_edit(request.user, schedule)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = target_svc.posted_from_request(request.POST)
        result = svc.save_target(request.user, schedule, posted)
        _raise_if_opaque(result)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_target", schedule_slug=schedule.slug)

    kind = posted.get("kind") or "file_gate"
    projects = target_svc.list_projects_for_kind(schedule.company, kind)
    pipelines = target_svc.list_pipelines(schedule.company)
    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "posted": posted,
            "errors": errors,
            "company": schedule.company,
            "can_edit": can_edit,
            "hub": hub,
            "job_kinds": target_svc.JOB_KINDS,
            "projects": projects,
            "pipelines": pipelines,
            "projects_url": reverse(
                "file_scheduler:schedule_target_projects",
                kwargs={"schedule_slug": schedule.slug},
            ),
        }
    )
    return render(request, "file_scheduler/target/target.html", ctx)


@_sch_view
def schedule_overlap_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/overlap/overlap_help.html", ctx)


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_overlap(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    form_ns = f"file_scheduler:overlap:{schedule_slug}"
    posted = {
        "overlap_policy": schedule.overlap_policy or Schedule.OVERLAP_SKIP,
    }
    errors: dict[str, list[str]] = {}
    can_edit = svc.user_can_edit(request.user, schedule)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = svc.overlap_posted_from_request(request.POST)
        result = svc.save_overlap(request.user, schedule, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_overlap", schedule_slug=schedule.slug)

    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "posted": posted,
            "errors": errors,
            "company": schedule.company,
            "can_edit": can_edit,
            "hub": hub,
        }
    )
    return render(request, "file_scheduler/overlap/overlap.html", ctx)


@_sch_view
def schedule_notify_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/notify/notify_help.html", ctx)


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_notify(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    form_ns = f"file_scheduler:notify:{schedule_slug}"
    posted = notify_svc.snapshot_from_schedule(schedule)
    errors: dict[str, list[str]] = {}
    can_edit = svc.user_can_edit(request.user, schedule)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = notify_svc.posted_from_request(request.POST)
        result = notify_svc.save_notify(request.user, schedule, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_notify", schedule_slug=schedule.slug)

    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "posted": posted,
            "errors": errors,
            "company": schedule.company,
            "can_edit": can_edit,
            "hub": hub,
            "members": notify_svc.member_choices(schedule),
        }
    )
    return render(request, "file_scheduler/notify/notify.html", ctx)


@_sch_view
def schedule_dependency_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/dependency/dependency_help.html", ctx)


@_sch_view
@require_http_methods(["GET", "POST"])
def schedule_dependency(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    form_ns = f"file_scheduler:dependency:{schedule_slug}"
    posted = dep_svc.snapshot_from_schedule(schedule)
    errors: dict[str, list[str]] = {}
    can_edit = svc.user_can_edit(request.user, schedule)

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = dep_svc.posted_from_request(request.POST)
        result = svc.save_dependency(request.user, schedule, posted)
        _raise_if_opaque(result)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_scheduler:schedule_dependency", schedule_slug=schedule.slug)

    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "posted": posted,
            "errors": errors,
            "company": schedule.company,
            "can_edit": can_edit,
            "hub": hub,
            "parent_projects": dep_svc.list_parent_projects(schedule.company),
            "parent_pipelines": [
                row for row in target_svc.list_pipelines(schedule.company) if row.get("eligible")
            ],
        }
    )
    return render(request, "file_scheduler/dependency/dependency.html", ctx)


@_sch_view
def schedule_activity_help(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    ctx = _sidebar()
    ctx.update({"schedule": schedule, "company": schedule.company})
    return render(request, "file_scheduler/activity/activity_help.html", ctx)


@_sch_view
def schedule_activity(request, schedule_slug: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    rows = [tick_svc.tick_row(t, user=request.user) for t in tick_svc.list_ticks(schedule)]
    stats = {
        "total": len(rows),
        "enqueued": sum(1 for r in rows if r["status"] == "enqueued"),
        "skipped": sum(1 for r in rows if r["status"] == "skipped"),
        "failed": sum(1 for r in rows if r["status"] == "failed"),
        "running": sum(1 for r in rows if r["status"] == "running"),
    }
    hub = svc.get_hub_context(request.user, schedule)
    ctx = _sidebar()
    ctx.update(
        {
            "schedule": schedule,
            "company": schedule.company,
            "hub": hub,
            "rows": rows,
            "stats": stats,
        }
    )
    return render(request, "file_scheduler/activity/activity.html", ctx)


@_sch_view
def schedule_module_pending(request, schedule_slug: str, module: str):
    schedule, bounced = _load_or_redirect(request, schedule_slug)
    if bounced:
        return bounced
    label = svc.PENDING_MODULES.get(module)
    if label is None:
        raise Http404()
    messages.info(request, svc.MSG_MODULE_PENDING)
    return redirect("file_scheduler:schedule_hub", schedule_slug=schedule.slug)
