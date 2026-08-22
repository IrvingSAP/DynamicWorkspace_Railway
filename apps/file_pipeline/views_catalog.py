from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.company.models import Company
from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.file_pipeline.services import pipeline_catalog_service as cat

FORM_CREATE = "file_pipeline:catalog:create"


def _ua(view_func):
    return security_complete_required(user_type_required("UA")(view_func))


def _read(view_func):
    return security_complete_required(user_type_required("UA", "US", "UF")(view_func))


def _can_manage(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.user_type == "UA")


def _ctx(request) -> dict:
    is_ua = _can_manage(request.user)
    return {
        "app_nav_active": "file_pipeline_catalog",
        "file_pipeline_nav_open": True,
        "is_ua": is_ua,
        "can_manage_catalog": is_ua,
    }


def _load_kind(kind: str):
    row = cat.get_row(kind)
    if row is None:
        return None
    return row


@_read
def catalog_list(request):
    q = request.GET.get("q", "").strip()
    enabled = request.GET.get("enabled", "all").strip() or "all"
    phase = request.GET.get("phase", "all").strip() or "all"
    rows = cat.list_kinds(q=q, enabled=enabled, phase=phase)
    ctx = _ctx(request)
    ctx.update(
        {
            "rows": rows,
            "stats": cat.catalog_stats(),
            "q": q,
            "enabled_filter": enabled,
            "phase_filter": phase,
            "shown": len(rows),
        }
    )
    return render(request, "file_pipeline/catalog/list.html", ctx)


@_read
def catalog_list_help(request):
    return render(request, "file_pipeline/catalog/list_help.html", _ctx(request))


@_ua
def catalog_create_help(request):
    return render(request, "file_pipeline/catalog/create_help.html", _ctx(request))


@_ua
@require_http_methods(["GET", "POST"])
def catalog_create(request):
    posted = cat.default_posted()
    errors: dict[str, list[str]] = {}
    if request.method == "GET":
        saved = take_form_state(request, FORM_CREATE)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)
    if request.method == "POST":
        posted = cat.posted_from_request(request.POST, include_kind=True)
        result = cat.create_kind(request.user, posted)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            messages.success(request, result.user_message)
            return redirect(
                "file_pipeline:catalog_detail",
                kind=result.payload["row"].kind,
            )
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_pipeline:catalog_create")
    ctx = _ctx(request)
    ctx.update(
        {
            "posted": posted,
            "errors": errors,
            "is_create": True,
            "posted_input_choices": cat.INPUT_CHOICES,
            "posted_output_choices": cat.OUTPUT_CHOICES,
        }
    )
    return render(request, "file_pipeline/catalog/form.html", ctx)


def _kind_or_list(request, kind: str):
    row = _load_kind(kind)
    if row is None:
        messages.error(request, cat.MSG_NOT_FOUND)
        return None, redirect("file_pipeline:catalog_list")
    return row, None


@_read
def catalog_detail(request, kind: str):
    row, bounced = _kind_or_list(request, kind)
    if bounced:
        return bounced
    ctx = _ctx(request)
    ctx.update(
        {
            "row": row,
            "draft_refs": cat.count_draft_references(row.kind),
        }
    )
    return render(request, "file_pipeline/catalog/detail.html", ctx)


@_read
def catalog_detail_help(request, kind: str):
    row, bounced = _kind_or_list(request, kind)
    if bounced:
        return bounced
    ctx = _ctx(request)
    ctx.update({"row": row})
    return render(request, "file_pipeline/catalog/detail_help.html", ctx)


@_ua
@require_http_methods(["GET", "POST"])
def catalog_edit(request, kind: str):
    row, bounced = _kind_or_list(request, kind)
    if bounced:
        return bounced
    form_ns = f"file_pipeline:catalog:edit:{kind}"
    posted = cat.posted_from_row(row)
    errors: dict[str, list[str]] = {}
    if request.method == "GET":
        saved = take_form_state(request, form_ns)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", errors)
    if request.method == "POST":
        posted = cat.posted_from_request(request.POST, include_kind=False)
        posted["kind"] = row.kind
        result = cat.update_kind(request.user, row, posted)
        if result.ok:
            clear_form_state(request, form_ns)
            messages.success(request, result.user_message)
            return redirect("file_pipeline:catalog_detail", kind=row.kind)
        errors = result.errors or {}
        stash_form_state(request, form_ns, posted, errors)
        messages.error(request, result.user_message)
        return redirect("file_pipeline:catalog_edit", kind=row.kind)
    ctx = _ctx(request)
    ctx.update(
        {
            "posted": posted,
            "errors": errors,
            "is_create": False,
            "row": row,
            "posted_input_choices": cat.INPUT_CHOICES,
            "posted_output_choices": cat.OUTPUT_CHOICES,
        }
    )
    return render(request, "file_pipeline/catalog/form.html", ctx)


@_ua
def catalog_edit_help(request, kind: str):
    row, bounced = _kind_or_list(request, kind)
    if bounced:
        return bounced
    ctx = _ctx(request)
    ctx.update({"row": row})
    return render(request, "file_pipeline/catalog/edit_help.html", ctx)


@_ua
@require_http_methods(["GET", "POST"])
def catalog_disable(request, kind: str):
    row, bounced = _kind_or_list(request, kind)
    if bounced:
        return bounced
    if request.method == "POST":
        result = cat.disable_kind(
            request.user,
            row,
            request.POST.get("reason", ""),
        )
        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return redirect("file_pipeline:catalog_detail", kind=row.kind)
    ctx = _ctx(request)
    ctx.update(
        {
            "row": row,
            "draft_refs": cat.count_draft_references(row.kind),
        }
    )
    return render(request, "file_pipeline/catalog/disable.html", ctx)


@_read
@require_http_methods(["GET", "POST"])
def catalog_company(request):
    is_ua = _can_manage(request.user)
    if is_ua:
        companies = list(Company.objects.filter(is_active=True).order_by("name_short"))
        company_id = request.GET.get("company") or request.POST.get("company") or ""
        company = None
        if company_id:
            company = next((c for c in companies if str(c.id) == str(company_id)), None)
        if company is None and companies:
            company = companies[0]
    else:
        companies = []
        company = request.user.profile.company
    if request.method == "POST":
        if not is_ua:
            messages.error(request, cat.MSG_UA_ONLY)
            return redirect("file_pipeline:catalog_company")
        if not company:
            return redirect("file_pipeline:catalog_company")
        result = cat.set_company_flag(
            request.user,
            company,
            request.POST.get("kind", "").strip(),
            request.POST.get("included") == "1",
        )
        if result.ok:
            messages.success(request, result.user_message)
        else:
            messages.error(request, result.user_message)
        return HttpResponseRedirect(
            reverse("file_pipeline:catalog_company") + f"?company={company.id}"
        )
    matrix = cat.company_kind_matrix(company) if company else []
    in_picker = sum(1 for item in matrix if item["in_designer"])
    blocked = sum(1 for item in matrix if not item["package_included"])
    off_cat = sum(1 for item in matrix if not item["catalog_on"])
    ctx = _ctx(request)
    ctx.update(
        {
            "companies": companies,
            "company": company,
            "matrix": matrix,
            "stats": {
                "in_picker": in_picker,
                "blocked": blocked,
                "off_cat": off_cat,
            },
        }
    )
    return render(request, "file_pipeline/catalog/company.html", ctx)


@_read
def catalog_company_help(request):
    return render(request, "file_pipeline/catalog/company_help.html", _ctx(request))
