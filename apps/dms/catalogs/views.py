from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import UserProfile
from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.dms.catalogs import catalog_registry
from apps.dms.catalogs.services import catalog_service


def _catalog_view(view_func):
    return security_complete_required(
        user_type_required("UA", "US", "UF")(view_func)
    )


def _catalog_manage_view(view_func):
    return security_complete_required(user_type_required("UA")(view_func))


def _form_namespace(catalog_slug: str, action: str, pk=None) -> str:
    if pk is not None:
        return f"dms:catalog:{catalog_slug}:{action}:{pk}"
    return f"dms:catalog:{catalog_slug}:{action}"


def _apply_flashed_form(request, namespace: str, posted: dict, errors: dict) -> tuple[dict, dict]:
    saved = take_form_state(request, namespace)
    if not saved:
        return posted, errors
    posted = {**posted, **saved.get("posted", {})}
    errors = saved.get("errors", errors)
    return posted, errors


def _sidebar_context(request, nav_active: str) -> dict:
    profile = request.user.profile
    return {
        "app_nav_active": nav_active,
        "filepipe_nav_open": nav_active.startswith("filepipe"),
        "is_ua": profile.user_type == UserProfile.USER_ADMIN,
    }


@_catalog_view
def hub(request):
    ctx = _sidebar_context(request, "filepipe_catalogs")
    ctx.update(
        {
            "catalogs": catalog_registry.hub_entries(),
            "stats": catalog_service.hub_stats(),
        }
    )
    return render(request, "dms/catalogs/hub.html", ctx)


@_catalog_view
def hub_help(request):
    ctx = _sidebar_context(request, "filepipe_catalogs")
    return render(request, "dms/catalogs/hub_help.html", ctx)


@_catalog_view
def list_view(request, catalog_slug: str):
    catalog = catalog_registry.get_catalog(catalog_slug)
    ctx = _sidebar_context(request, "filepipe_catalogs")
    items = catalog_service.list_items(catalog_slug)
    rows = [
        {
            "item": item,
            "cells": [
                {
                    "value": catalog_service.display_value(item, col.key),
                    "mono": col.mono,
                    "key": col.key,
                }
                for col in catalog.columns
            ],
        }
        for item in items
    ]
    ctx.update({"catalog": catalog, "rows": rows})
    return render(request, "dms/catalogs/list.html", ctx)


@_catalog_view
def list_help(request, catalog_slug: str):
    catalog = catalog_registry.get_catalog(catalog_slug)
    ctx = _sidebar_context(request, "filepipe_catalogs")
    ctx.update({"catalog": catalog})
    return render(request, "dms/catalogs/list_help.html", ctx)


@_catalog_manage_view
def form_help(request, catalog_slug: str):
    catalog = catalog_registry.get_catalog(catalog_slug)
    ctx = _sidebar_context(request, "filepipe_catalogs")
    ctx.update({"catalog": catalog})
    return render(request, "dms/catalogs/form_help.html", ctx)


@_catalog_manage_view
@require_http_methods(["GET", "POST"])
def create(request, catalog_slug: str):
    catalog = catalog_registry.get_catalog(catalog_slug)
    namespace = _form_namespace(catalog_slug, "create")
    posted = catalog_service.default_posted(catalog)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, namespace, posted, errors)

    if request.method == "POST":
        posted = catalog_service.posted_from_request(catalog, request.POST)
        result = catalog_service.create_catalog_item(catalog_slug, posted)
        if result.ok:
            clear_form_state(request, namespace)
            messages.success(request, result.user_message)
            return redirect("dms:catalog_list", catalog_slug=catalog_slug)
        errors = result.errors or {}
        stash_form_state(request, namespace, posted, errors)
        messages.error(request, result.user_message)
        return redirect("dms:catalog_create", catalog_slug=catalog_slug)

    ctx = _sidebar_context(request, "filepipe_catalogs")
    ctx.update({"catalog": catalog, "posted": posted, "errors": errors, "is_edit": False})
    return render(request, "dms/catalogs/form.html", ctx)


@_catalog_manage_view
@require_http_methods(["GET", "POST"])
def update(request, catalog_slug: str, pk):
    catalog = catalog_registry.get_catalog(catalog_slug)
    item = get_object_or_404(catalog.model, pk=pk)
    namespace = _form_namespace(catalog_slug, "update", pk)
    posted = catalog_service.instance_to_posted(catalog, item)
    errors: dict[str, list[str]] = {}

    if request.method == "GET":
        posted, errors = _apply_flashed_form(request, namespace, posted, errors)

    if request.method == "POST":
        posted = catalog_service.posted_from_request(catalog, request.POST)
        result = catalog_service.update_catalog_item(catalog_slug, item, posted)
        if result.ok:
            clear_form_state(request, namespace)
            messages.success(request, result.user_message)
            return redirect("dms:catalog_list", catalog_slug=catalog_slug)
        errors = result.errors or {}
        stash_form_state(request, namespace, posted, errors)
        messages.error(request, result.user_message)
        return redirect("dms:catalog_update", catalog_slug=catalog_slug, pk=pk)

    ctx = _sidebar_context(request, "filepipe_catalogs")
    ctx.update(
        {
            "catalog": catalog,
            "item": item,
            "posted": posted,
            "errors": errors,
            "is_edit": True,
        }
    )
    return render(request, "dms/catalogs/form.html", ctx)


@_catalog_manage_view
@require_http_methods(["POST"])
def deactivate(request, catalog_slug: str, pk):
    catalog = catalog_registry.get_catalog(catalog_slug)
    item = get_object_or_404(catalog.model, pk=pk)
    result = catalog_service.deactivate_catalog_item(catalog_slug, item)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("dms:catalog_list", catalog_slug=catalog_slug)
