from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.services import account_service
from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state

FORM_CREATE = "accounts:create"


def _form_namespace(action: str, pk=None) -> str:
    if pk is not None:
        return f"accounts:{action}:{pk}"
    return f"accounts:{action}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _accounts_view(view_func):
    return user_type_required("UA", "US")(security_complete_required(view_func))


def _sidebar_template(actor_profile) -> str:
    if actor_profile.user_type == "UA":
        return "includes/sidebar_ua.html"
    return "includes/sidebar_us.html"


@_accounts_view
def account_list(request):
    actor_profile = request.user.profile
    scope = account_service.get_management_scope(actor_profile)
    users, stats = account_service.list_with_stats(actor_profile)
    companies = (
        account_service.companies_for_picker()
        if scope["show_company_column"]
        else []
    )
    return render(
        request,
        "accounts/account_list.html",
        {
            "users": users,
            "stats": stats,
            "management_scope": scope,
            "companies": companies,
            "app_nav_active": "users",
            "sidebar_template": _sidebar_template(actor_profile),
        },
    )


@_accounts_view
@require_http_methods(["GET", "POST"])
def account_create(request):
    actor_profile = request.user.profile
    scope = account_service.get_management_scope(actor_profile)
    posted = account_service.default_posted(actor_profile)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, FORM_CREATE, posted, errors)

    if request.method == "POST":
        posted = account_service.posted_from_request(request.POST, actor_profile)
        result = account_service.create_user(actor_profile, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            return redirect("accounts:detail", pk=result.payload["profile"].pk)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("accounts:create")

    return render(
        request,
        "accounts/account_create.html",
        {
            "posted": posted,
            "errors": errors,
            "management_scope": scope,
            "companies": account_service.companies_for_picker(),
            "app_nav_active": "users",
            "sidebar_template": _sidebar_template(actor_profile),
            "is_edit": False,
        },
    )


@_accounts_view
def account_detail(request, pk):
    actor_profile = request.user.profile
    scope = account_service.get_management_scope(actor_profile)
    profile = account_service.get_manageable_user(actor_profile, pk)
    detail = account_service.get_detail_context(profile)
    return render(
        request,
        "accounts/account_detail.html",
        {
            "profile": profile,
            "detail": detail,
            "management_scope": scope,
            "app_nav_active": "users",
            "sidebar_template": _sidebar_template(actor_profile),
        },
    )


@_accounts_view
@require_http_methods(["GET", "POST"])
def account_update(request, pk):
    actor_profile = request.user.profile
    scope = account_service.get_management_scope(actor_profile)
    profile = account_service.get_manageable_user(actor_profile, pk)
    form_ns = _form_namespace("update", pk)
    posted = account_service.default_posted(actor_profile, profile)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = account_service.posted_from_request(
            request.POST, actor_profile, profile=profile
        )
        result = account_service.update_user(actor_profile, profile, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("accounts:detail", pk=profile.pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("accounts:update", pk=profile.pk)

    return render(
        request,
        "accounts/account_update.html",
        {
            "profile": profile,
            "posted": posted,
            "errors": errors,
            "management_scope": scope,
            "companies": account_service.companies_for_picker(),
            "app_nav_active": "users",
            "sidebar_template": _sidebar_template(actor_profile),
            "is_edit": True,
        },
    )


@_accounts_view
@require_http_methods(["GET", "POST"])
def account_password(request, pk):
    actor_profile = request.user.profile
    scope = account_service.get_management_scope(actor_profile)
    profile = account_service.get_manageable_user(actor_profile, pk)
    form_ns = _form_namespace("password", pk)
    posted = account_service.default_password_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = account_service.posted_password_from_request(request.POST)
        result = account_service.update_password(actor_profile, profile, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("accounts:detail", pk=profile.pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("accounts:password", pk=profile.pk)

    return render(
        request,
        "accounts/account_password.html",
        {
            "profile": profile,
            "posted": posted,
            "errors": errors,
            "management_scope": scope,
            "app_nav_active": "users",
            "sidebar_template": _sidebar_template(actor_profile),
        },
    )


@_accounts_view
@require_http_methods(["GET", "POST"])
def account_delete(request, pk):
    actor_profile = request.user.profile
    scope = account_service.get_management_scope(actor_profile)
    profile = account_service.get_manageable_user(actor_profile, pk)
    detail = account_service.get_delete_context(profile)

    if request.method == "POST":
        if "confirm" in request.POST and request.POST.get("confirm") != "1":
            messages.error(
                request,
                "Debe confirmar que entiende que la acción no se puede deshacer.",
            )
            return render(
                request,
                "accounts/account_confirm_delete.html",
                {
                    "profile": profile,
                    "detail": detail,
                    "management_scope": scope,
                    "app_nav_active": "users",
                    "sidebar_template": _sidebar_template(actor_profile),
                },
            )

        result = account_service.delete_user(actor_profile, profile)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("accounts:list")
        messages.error(request, result.user_message)
        return redirect("accounts:detail", pk=pk)

    return render(
        request,
        "accounts/account_confirm_delete.html",
        {
            "profile": profile,
            "detail": detail,
            "management_scope": scope,
            "app_nav_active": "users",
            "sidebar_template": _sidebar_template(actor_profile),
        },
    )
