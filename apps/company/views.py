from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import UserProfile
from apps.company.services import company_service
from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state

FORM_CREATE = "company:create"


def _form_namespace(action: str, pk=None) -> str:
    if pk is not None:
        return f"company:{action}:{pk}"
    return f"company:{action}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors

def _ua_view(view_func):
    return user_type_required("UA")(security_complete_required(view_func))


@_ua_view
def company_list(request):
    companies, stats = company_service.list_with_stats()
    return render(
        request,
        "company/company_list.html",
        {
            "companies": companies,
            "stats": stats,
            "app_nav_active": "company",
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def company_create(request):
    posted = company_service.default_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, FORM_CREATE, posted, errors)

    if request.method == "POST":
        posted = company_service.posted_from_request(request.POST, request.FILES)
        result = company_service.create_company(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            return redirect("company:detail", pk=result.payload["company"].pk)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("company:create")

    return render(
        request,
        "company/company_create.html",
        {
            "posted": posted,
            "errors": errors,
            "app_nav_active": "company",
            "is_edit": False,
        },
    )


@security_complete_required
@user_type_required("UA", "US")
def company_account(request):
    profile = request.user.profile

    if profile.user_type == UserProfile.USER_ADMIN:
        return redirect("company:list")

    company = get_object_or_404(
        company_service.queryset(),
        pk=profile.company_id,
    )
    account = company_service.get_account_context(company)
    return render(
        request,
        "company/company_account.html",
        {
            "company": company,
            "account": account,
            "app_nav_active": "accounts",
        },
    )


@security_complete_required
@user_type_required("UA", "US")
def company_detail(request, pk):
    company = get_object_or_404(company_service.queryset(), pk=pk)
    profile = request.user.profile
    can_manage = profile.user_type == UserProfile.USER_ADMIN

    if profile.user_type == UserProfile.USER_SYSTEM and company.pk != profile.company_id:
        messages.error(request, "No tiene acceso a este recurso.")
        return redirect("dashboard:home")

    detail = company_service.get_detail_context(company)
    return render(
        request,
        "company/company_detail.html",
        {
            "company": company,
            "detail": detail,
            "app_nav_active": "company",
            "can_manage": can_manage,
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def company_update(request, pk):
    company = get_object_or_404(company_service.queryset(), pk=pk)
    form_ns = _form_namespace("update", pk)
    posted = company_service.default_posted(company)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = company_service.posted_from_request(
            request.POST, request.FILES, company=company
        )
        result = company_service.update_company(request.user, company, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("company:detail", pk=company.pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("company:update", pk=company.pk)

    return render(
        request,
        "company/company_update.html",
        {
            "company": company,
            "posted": posted,
            "errors": errors,
            "app_nav_active": "company",
            "is_edit": True,
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def company_delete(request, pk):
    company = get_object_or_404(company_service.queryset(), pk=pk)

    if request.method == "POST":
        if "confirm" in request.POST and request.POST.get("confirm") != "1":
            messages.error(
                request,
                "Debe confirmar que entiende que la acción no se puede deshacer.",
            )
            detail = company_service.get_related_counts(company)
            return render(
                request,
                "company/company_confirm_delete.html",
                {
                    "company": company,
                    "detail": detail,
                    "app_nav_active": "company",
                },
            )

        result = company_service.delete_company(company)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("company:list")
        messages.error(request, result.user_message)
        return redirect("company:detail", pk=pk)

    detail = company_service.get_related_counts(company)
    return render(
        request,
        "company/company_confirm_delete.html",
        {
            "company": company,
            "detail": detail,
            "app_nav_active": "company",
        },
    )
