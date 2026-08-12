from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.decorators import security_complete_required, user_type_required
from apps.dms.source_profile.services import source_persistence_service
from apps.file_split_merge.projects.services import split_merge_project_service
from apps.file_split_merge.publish.services import split_merge_publish_service
from apps.projects.services import project_service

MSG_NO_ACCESS = split_merge_project_service.MSG_NO_ACCESS


def _publish_view(view_func):
    return security_complete_required(user_type_required("UF")(view_func))


def _get_project_or_redirect(request, project_slug: str):
    project = split_merge_project_service.get_project_for_user(request.user, project_slug)
    if project is None:
        messages.error(request, MSG_NO_ACCESS)
        return None
    return project


def _sidebar() -> dict:
    return {
        "app_nav_active": "file_split_merge",
        "file_split_merge_nav_open": True,
    }


def _base_context(request, project) -> dict:
    membership = project_service.get_membership(request.user, project)
    hub = split_merge_publish_service.get_hub_context(request.user, project, membership)
    ctx = _sidebar()
    ctx.update(
        {
            "project": project,
            "membership": membership,
            "publish_hub": hub,
            "can_edit_definition": source_persistence_service.user_can_edit_source(
                request.user, project
            ),
            "publish_url": reverse(
                "file_split_merge:publish_action", kwargs={"project_slug": project.slug}
            ),
            "company": project.company,
        }
    )
    return ctx


@_publish_view
def hub(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    return render(
        request, "file_split_merge/publish/hub.html", _base_context(request, project)
    )


@_publish_view
def hub_help(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        return redirect("file_split_merge:project_list")
    return render(
        request,
        "file_split_merge/publish/hub_help.html",
        _base_context(request, project),
    )


@_publish_view
@require_http_methods(["POST"])
def publish_action(request, project_slug: str):
    project = _get_project_or_redirect(request, project_slug)
    if project is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": MSG_NO_ACCESS}, status=403)
        return redirect("file_split_merge:project_list")

    result = split_merge_publish_service.publish_sm_definition(request.user, project)
    redirect_to = request.POST.get("next", "").strip()
    if not redirect_to:
        redirect_to = reverse(
            "file_split_merge:publish_hub", kwargs={"project_slug": project_slug}
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if result.ok:
            payload = result.payload or {}
            return JsonResponse(
                {
                    "ok": True,
                    "message": result.user_message,
                    "published_version_number": payload.get("published_version_number"),
                    "new_draft_version_number": payload.get("new_draft_version_number"),
                    "warnings": payload.get("warning_messages") or [],
                }
            )
        payload = result.payload or {}
        return JsonResponse(
            {
                "ok": False,
                "message": result.user_message,
                "errors": result.errors or {},
                "rule_issues": payload.get("rule_issues") or [],
                "warnings": source_persistence_service.flatten_validation_messages(
                    payload.get("warnings")
                ),
            },
            status=400,
        )

    if result.ok:
        messages.success(request, result.user_message)
        for warning in (result.payload or {}).get("warning_messages") or []:
            messages.warning(request, warning)
    else:
        messages.error(request, result.user_message)
        issues = (result.payload or {}).get("rule_issues") or []
        for issue in issues[:5]:
            field = issue.get("field_name") or "global"
            detail = "; ".join(issue.get("messages") or [])
            messages.warning(
                request,
                f"{issue.get('code')} → {field}: {detail}",
            )
    return redirect(redirect_to)
