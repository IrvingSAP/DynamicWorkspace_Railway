from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.catalogs.services.permission_package_service import role_choices_for_ui
from apps.file_watch.models import WatchMembership
from apps.file_watch.services import watch_lifecycle_service as svc

FORM_CREATE = "file_watch:create"

MSG_NO_ACCESS = svc.MSG_NO_ACCESS
MSG_PA_ONLY = svc.MSG_PA_ONLY


def _sidebar() -> dict:
    return {
        "app_nav_active": "file_watch",
        "file_watch_nav_open": True,
    }


def _wach_view(view_func):
    return security_complete_required(user_type_required("US", "UF")(view_func))


def _watch_role_choices() -> list[dict]:
    allowed = WatchMembership.WATCH_ROLES
    items = [item for item in role_choices_for_ui() if item.get("code") in allowed]
    if items:
        return items
    return [
        {"code": code, "label": label, "maps_to_role": code}
        for code, label in WatchMembership.ROLE_CHOICES
    ]


@_wach_view
def watch_guide(request):
    profile = request.user.profile
    ctx = _sidebar()
    ctx.update(
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "file_watch_guide",
            "can_create": svc.user_can_create(request.user),
        }
    )
    return render(request, "file_watch/guide.html", ctx)


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_list(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        slug = (request.POST.get("watch_slug") or "").strip()
        watch = svc.get_watch_for_user(request.user, slug) if slug else None
        if watch is None:
            raise Http404()
        result = None
        if action == "archive":
            result = svc.archive_watch(request.user, watch)
        elif action == "pause":
            result = svc.pause_watch(request.user, watch)
        elif action == "resume":
            result = svc.resume_watch(request.user, watch)
        if result is not None:
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
        return redirect("file_watch:watch_list")
    rows, stats = svc.list_watches(request.user)
    ctx = _sidebar()
    ctx.update(
        {
            "rows": rows,
            "stats": stats,
            "company": request.user.profile.company,
            "can_create": svc.user_can_create(request.user),
        }
    )
    return render(request, "file_watch/projects/list.html", ctx)


@_wach_view
def watch_list_help(request):
    ctx = _sidebar()
    ctx.update({"can_create": svc.user_can_create(request.user)})
    return render(request, "file_watch/projects/list_help.html", ctx)


@_wach_view
def watch_create_help(request):
    if not svc.user_can_create(request.user):
        messages.error(request, svc.MSG_CREATE_FORBIDDEN)
        return redirect("file_watch:watch_list")
    return render(request, "file_watch/projects/create_help.html", _sidebar())


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_create(request):
    if not svc.user_can_create(request.user):
        messages.error(request, svc.MSG_CREATE_FORBIDDEN)
        return redirect("file_watch:watch_list")

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
        result = svc.create_watch(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            watch = result.payload["watch"]
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_create")

    ctx = _sidebar()
    ctx.update({"posted": posted, "errors": errors, "company": company})
    return render(request, "file_watch/projects/create.html", ctx)


def _load_or_404(request, watch_slug: str):
    watch = svc.get_watch_for_user(request.user, watch_slug)
    if watch is None:
        raise Http404()
    return watch


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_hub(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "pause":
            result = svc.pause_watch(request.user, watch)
        elif action == "resume":
            result = svc.resume_watch(request.user, watch)
        elif action == "activate":
            result = svc.activate_watch(request.user, watch)
        elif action == "archive":
            result = svc.archive_watch(request.user, watch)
        else:
            result = None
        if result is not None:
            if result.ok:
                messages.success(request, result.user_message)
                if action == "archive":
                    return redirect("file_watch:watch_list")
            else:
                messages.error(request, result.user_message)
        return redirect("file_watch:watch_hub", watch_slug=watch.slug)
    hub = svc.get_hub_context(request.user, watch)
    ctx = _sidebar()
    ctx.update({"watch": watch, "hub": hub, "company": watch.company})
    return render(request, "file_watch/projects/hub.html", ctx)


@_wach_view
def watch_hub_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    ctx = _sidebar()
    ctx.update({"watch": watch, "company": watch.company})
    return render(request, "file_watch/projects/hub_help.html", ctx)


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_edit(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    if not svc.user_can_edit(request.user, watch):
        messages.error(request, svc.MSG_FORBIDDEN)
        return redirect("file_watch:watch_hub", watch_slug=watch.slug)

    form_ns = f"file_watch:edit:{watch_slug}"
    posted = {
        "name": watch.name,
        "slug": watch.slug,
        "description": watch.description,
        "visibility": watch.visibility,
    }
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = svc.posted_from_request(request.POST)
        posted["slug"] = watch.slug
        result = svc.update_watch(request.user, watch, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_edit", watch_slug=watch.slug)

    ctx = _sidebar()
    ctx.update(
        {
            "watch": watch,
            "posted": posted,
            "errors": errors,
            "company": watch.company,
        }
    )
    return render(request, "file_watch/projects/edit.html", ctx)


@_wach_view
def watch_edit_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    ctx = _sidebar()
    ctx.update({"watch": watch, "company": watch.company})
    return render(request, "file_watch/projects/edit_help.html", ctx)


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_members(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    if not svc.user_can_manage_members(request.user, watch):
        messages.error(request, MSG_PA_ONLY)
        return redirect("file_watch:watch_hub", watch_slug=watch_slug)

    form_ns = f"file_watch:members:{watch_slug}"
    invite_posted = {"user_id": "", "role": WatchMembership.ROLE_ED}
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
            result = svc.invite_member(request.user, watch, invite_posted)
            if result.ok:
                clear_form_state(request, form_ns)
                messages.success(request, result.user_message)
            else:
                invite_errors = result.errors or {}
                stash_form_state(request, form_ns, invite_posted, invite_errors)
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_members", watch_slug=watch_slug)
        if action == "revoke":
            result = svc.set_member_active(
                request.user,
                watch,
                request.POST.get("membership_id", ""),
                active=False,
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_members", watch_slug=watch_slug)
        if action == "reactivate":
            result = svc.set_member_active(
                request.user,
                watch,
                request.POST.get("membership_id", ""),
                active=True,
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_members", watch_slug=watch_slug)
        if action == "change_role":
            result = svc.update_member_role(
                request.user,
                watch,
                request.POST.get("membership_id", ""),
                request.POST.get("role", "").strip(),
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_members", watch_slug=watch_slug)

    hub = svc.get_hub_context(request.user, watch)
    ctx = _sidebar()
    ctx.update(
        {
            "watch": watch,
            "hub": hub,
            "members": svc.list_members(watch),
            "invite_posted": invite_posted,
            "invite_errors": invite_errors,
            "role_choices": _watch_role_choices(),
            "company": watch.company,
        }
    )
    return render(request, "file_watch/projects/members.html", ctx)


@_wach_view
def watch_members_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    if not svc.user_can_manage_members(request.user, watch):
        messages.error(request, MSG_PA_ONLY)
        return redirect("file_watch:watch_hub", watch_slug=watch_slug)
    ctx = _sidebar()
    ctx.update({"watch": watch, "company": watch.company})
    return render(request, "file_watch/projects/members_help.html", ctx)


@_wach_view
def watch_member_search(request, watch_slug: str):
    watch = svc.get_watch_for_user(request.user, watch_slug)
    if watch is None:
        return JsonResponse({"results": [], "error": MSG_NO_ACCESS}, status=403)
    if not svc.user_can_manage_members(request.user, watch):
        return JsonResponse({"results": [], "error": MSG_PA_ONLY}, status=403)
    results = svc.search_invitable(request.user, watch, request.GET.get("q", ""))
    return JsonResponse({"results": results})


def _raise_if_opaque(result):
    from apps.file_watch.services import watch_errors as err

    if result is not None and not result.ok and result.error_code in err.OPAQUE_CODES:
        raise Http404()


def _module_ctx(request, watch, *, posted=None, errors=None, **extra):
    hub = svc.get_hub_context(request.user, watch)
    ctx = _sidebar()
    ctx.update(
        {
            "watch": watch,
            "hub": hub,
            "company": watch.company,
            "can_edit": svc.user_can_edit(request.user, watch),
            "posted": posted or {},
            "errors": errors or {},
        }
    )
    ctx.update(extra)
    return ctx


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_source(request, watch_slug: str):
    from apps.file_watch.services import watch_source as source_svc

    watch = _load_or_404(request, watch_slug)
    form_ns = f"file_watch:source:{watch_slug}"
    posted = source_svc.snapshot_from_watch(watch)
    errors: dict[str, list[str]] = {}
    push_token_once = ""

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)
            push_token_once = saved.get("posted", {}).get("_push_token_once", "")

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "test_sftp":
            result = source_svc.test_sftp_connection(
                request.user, watch, source_svc.posted_from_request(request.POST)
            )
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_source", watch_slug=watch.slug)
        if action == "rotate_token":
            result = source_svc.rotate_push_token(request.user, watch)
            if result.ok:
                messages.success(request, result.user_message)
                token = (result.payload or {}).get("push_token_once", "")
                stash_form_state(
                    request,
                    form_ns,
                    {**source_svc.snapshot_from_watch(watch), "_push_token_once": token},
                    {},
                )
            else:
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_source", watch_slug=watch.slug)
        posted = source_svc.posted_from_request(request.POST)
        result = source_svc.update_source(request.user, watch, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            token = (result.payload or {}).get("push_token_once", "")
            if token:
                stash_form_state(
                    request,
                    form_ns,
                    {**source_svc.snapshot_from_watch(result.payload["watch"]), "_push_token_once": token},
                    {},
                )
            return redirect("file_watch:watch_source", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_source", watch_slug=watch.slug)

    return render(
        request,
        "file_watch/source/source.html",
        _module_ctx(request, watch, posted=posted, errors=errors, push_token_once=push_token_once),
    )


@_wach_view
def watch_source_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(request, "file_watch/source/source_help.html", _module_ctx(request, watch))


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_intake(request, watch_slug: str):
    from apps.file_watch.services import watch_intake as intake_svc

    watch = _load_or_404(request, watch_slug)
    form_ns = f"file_watch:intake:{watch_slug}"
    posted = intake_svc.snapshot_policy(watch)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = intake_svc.posted_policy(request.POST)
        result = intake_svc.update_intake_policy(request.user, watch, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_watch:watch_intake", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_intake", watch_slug=watch.slug)

    status = (request.GET.get("status") or "").strip()
    batches = intake_svc.list_batches(watch, status=status)
    return render(
        request,
        "file_watch/intake/intake.html",
        _module_ctx(
            request,
            watch,
            posted=posted,
            errors=errors,
            batches=batches,
            status_filter=status,
        ),
    )


@_wach_view
def watch_intake_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(request, "file_watch/intake/intake_help.html", _module_ctx(request, watch))


@_wach_view
def watch_batches(request, watch_slug: str):
    from django.urls import reverse

    url = reverse("file_watch:watch_intake", kwargs={"watch_slug": watch_slug})
    return redirect(f"{url}#lotes")


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_route(request, watch_slug: str):
    from apps.file_scheduler.services import schedule_target as target_svc
    from apps.file_watch.services import watch_route as route_svc
    from django.urls import reverse

    watch = _load_or_404(request, watch_slug)
    form_ns = f"file_watch:route:{watch_slug}"
    posted = route_svc.snapshot_from_watch(watch)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = route_svc.posted_from_request(request.POST)
        result = route_svc.save_route(request.user, watch, posted)
        _raise_if_opaque(result)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_route", watch_slug=watch.slug)

    kind = posted.get("kind") or "file_gate"
    return render(
        request,
        "file_watch/route/route.html",
        _module_ctx(
            request,
            watch,
            posted=posted,
            errors=errors,
            job_kinds=target_svc.JOB_KINDS,
            projects=target_svc.list_projects_for_kind(watch.company, kind),
            pipelines=target_svc.list_pipelines(watch.company),
            projects_url=reverse(
                "file_watch:watch_route_projects",
                kwargs={"watch_slug": watch.slug},
            ),
        ),
    )


@_wach_view
@require_GET
def watch_route_projects(request, watch_slug: str):
    from apps.file_scheduler.services import schedule_target as target_svc

    watch = svc.get_watch_for_user(request.user, watch_slug)
    if watch is None:
        return JsonResponse({"ok": False, "projects": []}, status=403)
    kind = (request.GET.get("kind") or "").strip()
    rows = target_svc.list_projects_for_kind(watch.company, kind)
    return JsonResponse({"ok": True, "projects": rows})


@_wach_view
def watch_route_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(request, "file_watch/route/route_help.html", _module_ctx(request, watch))


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_fire(request, watch_slug: str):
    from apps.file_watch.services import watch_fire as fire_svc

    watch = _load_or_404(request, watch_slug)
    form_ns = f"file_watch:fire:{watch_slug}"
    posted = fire_svc.snapshot_from_watch(watch)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "activate":
            result = svc.activate_watch(request.user, watch)
            if result.ok:
                messages.success(request, result.user_message)
            else:
                messages.error(request, result.user_message)
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        posted = fire_svc.posted_from_request(request.POST)
        result = fire_svc.save_fire(request.user, watch, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_fire", watch_slug=watch.slug)

    return render(
        request,
        "file_watch/fire/fire.html",
        _module_ctx(
            request,
            watch,
            posted=posted,
            errors=errors,
            route_is_defer=watch.route_mode == watch.ROUTE_DEFER,
        ),
    )


@_wach_view
def watch_fire_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(request, "file_watch/fire/fire_help.html", _module_ctx(request, watch))


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_idempotency(request, watch_slug: str):
    from apps.file_watch.services import watch_idempotency as idem_svc

    watch = _load_or_404(request, watch_slug)
    form_ns = f"file_watch:idempotency:{watch_slug}"
    posted = idem_svc.snapshot_from_watch(watch)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = idem_svc.posted_from_request(request.POST)
        result = idem_svc.save_idempotency(request.user, watch, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_idempotency", watch_slug=watch.slug)

    return render(
        request,
        "file_watch/idempotency/idempotency.html",
        _module_ctx(request, watch, posted=posted, errors=errors),
    )


@_wach_view
def watch_idempotency_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(
        request, "file_watch/idempotency/idempotency_help.html", _module_ctx(request, watch)
    )


@_wach_view
@require_http_methods(["GET", "POST"])
def watch_notify(request, watch_slug: str):
    from apps.file_watch.services import watch_notify as notify_svc

    watch = _load_or_404(request, watch_slug)
    form_ns = f"file_watch:notify:{watch_slug}"
    posted = notify_svc.snapshot_from_watch(watch)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)

    if request.method == "POST":
        posted = notify_svc.posted_from_request(request.POST)
        result = notify_svc.save_notify(request.user, watch, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_watch:watch_hub", watch_slug=watch.slug)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_watch:watch_notify", watch_slug=watch.slug)

    return render(
        request,
        "file_watch/notify/notify.html",
        _module_ctx(
            request,
            watch,
            posted=posted,
            errors=errors,
            members=notify_svc.member_choices(watch),
        ),
    )


@_wach_view
def watch_notify_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(request, "file_watch/notify/notify_help.html", _module_ctx(request, watch))


@_wach_view
def watch_audit(request, watch_slug: str):
    from apps.file_watch.services import watch_audit as audit_svc

    watch = _load_or_404(request, watch_slug)
    rows = audit_svc.list_audit_rows(watch)
    return render(
        request,
        "file_watch/audit/audit.html",
        _module_ctx(request, watch, rows=rows),
    )


@_wach_view
def watch_audit_help(request, watch_slug: str):
    watch = _load_or_404(request, watch_slug)
    return render(request, "file_watch/audit/audit_help.html", _module_ctx(request, watch))


@_wach_view
def watch_errors(request):
    from apps.file_watch.services import watch_errors as err

    ctx = _sidebar()
    ctx.update(
        {
            "company": request.user.profile.company,
            "rows": err.catalog_rows(),
            "app_nav_active": "file_watch",
        }
    )
    return render(request, "file_watch/errors/errors.html", ctx)


@_wach_view
def watch_errors_help(request):
    ctx = _sidebar()
    ctx.update({"company": request.user.profile.company})
    return render(request, "file_watch/errors/errors_help.html", ctx)


@_wach_view
def watch_integration(request):
    from apps.file_watch.services import watch_integration as integ_svc

    ctx = _sidebar()
    ctx.update(
        {
            "company": request.user.profile.company,
            "integ": integ_svc.map_context(),
            "app_nav_active": "file_watch",
        }
    )
    return render(request, "file_watch/integration/integration.html", ctx)


@_wach_view
def watch_integration_help(request):
    ctx = _sidebar()
    ctx.update({"company": request.user.profile.company})
    return render(request, "file_watch/integration/integration_help.html", ctx)


@csrf_exempt
@_wach_view
@require_http_methods(["POST"])
def watch_api_push(request, watch_slug: str):
    """Ingesta por API push (sesión autenticada o token de bandeja)."""
    from apps.file_watch.models import Watch
    from apps.file_watch.services import watch_intake as intake_svc

    company = request.user.profile.company
    try:
        watch = Watch.objects.get(company=company, slug=watch_slug)
    except Watch.DoesNotExist:
        raise Http404()

    token = (
        request.headers.get("X-Watch-Token")
        or request.META.get("HTTP_X_WATCH_TOKEN")
        or request.POST.get("token")
        or ""
    ).strip()
    authed = svc.user_can_edit(request.user, watch) or svc.user_can_view(
        request.user, watch
    )
    token_ok = bool(watch.push_token) and secrets_compare(watch.push_token, token)
    if not (authed or token_ok):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    if watch.source_kind != Watch.SOURCE_API_PUSH:
        return JsonResponse({"ok": False, "error": "source_kind"}, status=400)
    if watch.status != Watch.STATUS_ACTIVE:
        return JsonResponse({"ok": False, "error": "inactive"}, status=400)

    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"ok": False, "error": "file_required"}, status=400)
    data = upload.read()
    result = intake_svc.ingest_bytes(
        watch, upload.name, data, source_kind=Watch.SOURCE_API_PUSH
    )
    if not result.ok and not (result.payload or {}).get("skipped"):
        return JsonResponse(
            {
                "ok": False,
                "error_code": result.error_code,
                "user_message": result.user_message,
            },
            status=400,
        )
    batch = (result.payload or {}).get("batch")
    return JsonResponse(
        {
            "ok": True,
            "skipped": bool((result.payload or {}).get("skipped")),
            "batch_id": str(batch.id) if batch else "",
            "content_hash": getattr(batch, "content_hash", "") if batch else "",
        }
    )


def secrets_compare(stored: str, given: str) -> bool:
    import hmac

    if not stored or not given:
        return False
    return hmac.compare_digest(stored, given)


@_wach_view
def watch_module_pending(request, watch_slug: str, module: str):
    watch = _load_or_404(request, watch_slug)
    label = svc.PENDING_MODULES.get(module)
    if label is None:
        raise Http404()
    messages.info(request, f"{label}: {svc.MSG_MODULE_PENDING}")
    return redirect("file_watch:watch_hub", watch_slug=watch.slug)
