from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.billing.models import Plan, Subscription
from apps.billing.services import (
    payment_service,
    plan_service,
    subscription_service,
)
from apps.company.models import Company
from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state


def _form_namespace(section: str, action: str, pk=None) -> str:
    if pk is not None:
        return f"billing:{section}:{action}:{pk}"
    return f"billing:{section}:{action}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _ua_view(view_func):
    return user_type_required("UA")(security_complete_required(view_func))


def _billing_nav(section: str) -> str:
    return {
        "plans": "billing_plans",
        "subscriptions": "billing_subscriptions",
        "payments": "billing_payments",
    }.get(section, "billing")


# --- Planes ---


@_ua_view
def plan_list(request):
    plans, stats = plan_service.list_with_stats()
    return render(
        request,
        "billing/plan_list.html",
        {
            "plans": plans,
            "stats": stats,
            "app_nav_active": _billing_nav("plans"),
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def plan_create(request):
    form_ns = _form_namespace("plan", "create")
    posted = plan_service.default_posted()
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = plan_service.posted_from_request(request.POST)
        result = plan_service.create_plan(request.user, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("billing:plan_detail", pk=result.payload["plan"].pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("billing:plan_create")

    return render(
        request,
        "billing/plan_create.html",
        {
            "posted": posted,
            "errors": errors,
            "app_nav_active": _billing_nav("plans"),
            "is_edit": False,
        },
    )


@_ua_view
def plan_detail(request, pk):
    plan = get_object_or_404(plan_service.queryset(), pk=pk)
    subscriptions = list(
        plan.subscriptions.select_related("company").order_by("company__name_short")
    )
    return render(
        request,
        "billing/plan_detail.html",
        {
            "plan": plan,
            "subscriptions": subscriptions,
            "app_nav_active": _billing_nav("plans"),
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def plan_update(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    form_ns = _form_namespace("plan", "update", pk)
    posted = plan_service.default_posted(plan)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = plan_service.posted_from_request(request.POST, plan=plan)
        result = plan_service.update_plan(request.user, plan, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("billing:plan_detail", pk=plan.pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("billing:plan_update", pk=pk)

    return render(
        request,
        "billing/plan_update.html",
        {
            "plan": plan,
            "posted": posted,
            "errors": errors,
            "app_nav_active": _billing_nav("plans"),
            "is_edit": True,
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    subscriptions_count = plan.subscriptions.count()

    if request.method == "POST":
        result = plan_service.delete_plan(plan)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("billing:plan_list")
        messages.error(request, result.user_message)
        return redirect("billing:plan_detail", pk=pk)

    return render(
        request,
        "billing/plan_confirm_delete.html",
        {
            "plan": plan,
            "subscriptions_count": subscriptions_count,
            "app_nav_active": _billing_nav("plans"),
        },
    )


# --- Suscripciones ---


def _get_subscription_by_company(company_pk):
    company = get_object_or_404(Company, pk=company_pk)
    subscription = get_object_or_404(
        subscription_service.queryset(),
        company=company,
    )
    return company, subscription


@_ua_view
def subscription_list(request):
    subscriptions, stats = subscription_service.list_with_stats()
    return render(
        request,
        "billing/subscription_list.html",
        {
            "subscriptions": subscriptions,
            "stats": stats,
            "app_nav_active": _billing_nav("subscriptions"),
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def subscription_create(request):
    form_ns = _form_namespace("subscription", "create")
    posted = subscription_service.default_posted()
    errors: dict[str, list[str]] = {}
    companies = subscription_service.companies_without_subscription()
    plans = subscription_service.active_plans()

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = subscription_service.posted_from_request(request.POST)
        result = subscription_service.create_subscription(request.user, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            subscription = result.payload["subscription"]
            return redirect(
                "billing:subscription_detail",
                company_pk=subscription.company_id,
            )
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("billing:subscription_create")

    return render(
        request,
        "billing/subscription_create.html",
        {
            "posted": posted,
            "errors": errors,
            "companies": companies,
            "plans": plans,
            "app_nav_active": _billing_nav("subscriptions"),
        },
    )


@_ua_view
def subscription_detail(request, company_pk):
    company, subscription = _get_subscription_by_company(company_pk)
    detail = subscription_service.get_detail_context(subscription)
    return render(
        request,
        "billing/subscription_detail.html",
        {
            "company": company,
            "subscription": subscription,
            "detail": detail,
            "app_nav_active": _billing_nav("subscriptions"),
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def subscription_update(request, company_pk):
    company, subscription = _get_subscription_by_company(company_pk)
    form_ns = _form_namespace("subscription", "update", company_pk)
    posted = subscription_service.default_posted(subscription)
    errors: dict[str, list[str]] = {}
    plans = Plan.objects.order_by("code")

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)

    if request.method == "POST":
        posted = subscription_service.posted_from_request(
            request.POST,
            subscription=subscription,
        )
        result = subscription_service.update_subscription(
            request.user,
            subscription,
            posted,
        )
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("billing:subscription_detail", company_pk=company_pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("billing:subscription_update", company_pk=company_pk)

    return render(
        request,
        "billing/subscription_update.html",
        {
            "company": company,
            "subscription": subscription,
            "posted": posted,
            "errors": errors,
            "plans": plans,
            "app_nav_active": _billing_nav("subscriptions"),
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def subscription_delete(request, company_pk):
    company, subscription = _get_subscription_by_company(company_pk)

    if request.method == "POST":
        result = subscription_service.delete_subscription(subscription)
        messages.success(request, result.user_message)
        return redirect("billing:subscription_list")

    return render(
        request,
        "billing/subscription_confirm_delete.html",
        {
            "company": company,
            "subscription": subscription,
            "app_nav_active": _billing_nav("subscriptions"),
        },
    )


# --- Pagos ---


@_ua_view
def payment_list(request):
    payments, stats = payment_service.list_with_stats()
    return render(
        request,
        "billing/payment_list.html",
        {
            "payments": payments,
            "stats": stats,
            "app_nav_active": _billing_nav("payments"),
        },
    )


@_ua_view
@require_http_methods(["GET", "POST"])
def payment_create(request):
    form_ns = _form_namespace("payment", "create")
    posted = payment_service.default_posted()
    errors: dict[str, list[str]] = {}
    subscriptions = payment_service.eligible_subscriptions()

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, form_ns, posted, errors)
        preselect = request.GET.get("subscription", "").strip()
        if preselect and not posted.get("subscription_id"):
            posted["subscription_id"] = preselect

    if request.method == "POST":
        posted = payment_service.posted_from_request(request.POST)
        result = payment_service.create_payment(request.user, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("billing:payment_detail", pk=result.payload["payment"].pk)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("billing:payment_create")

    return render(
        request,
        "billing/payment_create.html",
        {
            "posted": posted,
            "errors": errors,
            "subscriptions": subscriptions,
            "app_nav_active": _billing_nav("payments"),
        },
    )


@_ua_view
def payment_detail(request, pk):
    payment = get_object_or_404(payment_service.queryset(), pk=pk)
    return render(
        request,
        "billing/payment_detail.html",
        {
            "payment": payment,
            "app_nav_active": _billing_nav("payments"),
        },
    )
