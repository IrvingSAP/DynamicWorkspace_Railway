from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.decorators import security_complete_required, user_type_required
from apps.core.services.form_flash import clear_form_state, stash_form_state, take_form_state
from apps.platform_api.models import (
    ALL_SCOPES,
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_ARTIFACT_TTL_HOURS,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_RATE_PER_MINUTE,
    SCOPE_LABELS,
    WEBHOOK_EVENTS,
    WEBHOOK_EVENT_LABELS,
)
from apps.platform_api.services import (
    api_client_service,
    client_audit_service,
    contract_service,
    integration_service,
    openapi_service,
    process_security_service,
    webhook_service,
)

FORM_CREATE = "platform_api:create"
REVEAL_SESSION = "platform_api_plaintext_key"
WEBHOOK_SECRET_SESSION = "platform_api_webhook_secret"


def _us_view(view_func):
    return user_type_required("US")(security_complete_required(view_func))


def _ctx(**extra):
    return {
        "app_nav_active": "platform_api",
        "scope_choices": [(s, SCOPE_LABELS[s]) for s in ALL_SCOPES],
        "webhook_event_choices": [(e, WEBHOOK_EVENT_LABELS[e]) for e in WEBHOOK_EVENTS],
        **extra,
    }


@_us_view
def client_list_help(request):
    return render(request, "platform_api/clients/list_help.html", _ctx())


@_us_view
def client_create_help(request):
    return render(request, "platform_api/clients/create_help.html", _ctx())


def _client_help(request, pk, template):
    client = api_client_service.get_for_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    return render(request, template, _ctx(client=client))


@_us_view
def client_detail_help(request, pk):
    return _client_help(request, pk, "platform_api/clients/detail_help.html")


@_us_view
def client_reveal_help(request, pk):
    return _client_help(request, pk, "platform_api/clients/reveal_help.html")


@_us_view
def client_list(request):
    clients, stats = api_client_service.list_for_user(request.user)
    return render(
        request,
        "platform_api/clients/list.html",
        _ctx(clients=clients, stats=stats),
    )


@_us_view
@require_http_methods(["GET", "POST"])
def client_create(request):
    posted = api_client_service.default_posted()
    errors: dict = {}
    if request.method == "GET":
        saved = take_form_state(request, FORM_CREATE)
        if saved:
            posted = {**posted, **saved.get("posted", {})}
            errors = saved.get("errors", {})
    if request.method == "POST":
        posted = api_client_service.posted_from_request(request.POST)
        result = api_client_service.create_client(request.user, posted, request=request)
        if result.ok:
            clear_form_state(request, FORM_CREATE)
            request.session[REVEAL_SESSION] = {
                "client_id": str(result.payload["client"].pk),
                "plaintext_key": result.payload["plaintext_key"],
            }
            messages.success(request, result.user_message)
            return redirect("platform_api:client_reveal", pk=result.payload["client"].pk)
        errors = result.errors or {}
        stash_form_state(request, FORM_CREATE, posted, errors)
        messages.error(request, result.user_message)
        return redirect("platform_api:client_create")
    return render(
        request,
        "platform_api/clients/create.html",
        _ctx(posted=posted, errors=errors),
    )


@_us_view
def client_reveal(request, pk):
    client = api_client_service.get_for_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    bag = request.session.pop(REVEAL_SESSION, None) or {}
    plaintext = ""
    if str(bag.get("client_id")) == str(client.pk):
        plaintext = bag.get("plaintext_key") or ""
    if not plaintext:
        messages.warning(
            request,
            "La key ya no está disponible en pantalla. Si la perdió, rote la credencial.",
        )
        return redirect("platform_api:client_detail", pk=client.pk)
    from apps.platform_api.models import ACTION_KEY_REVEALED

    client_audit_service.record_event(
        client=client,
        action=ACTION_KEY_REVEALED,
        actor=request.user,
        request=request,
        after=client_audit_service.snapshot_client(client),
    )
    return render(
        request,
        "platform_api/clients/reveal.html",
        _ctx(client=client, plaintext_key=plaintext),
    )


@_us_view
@require_http_methods(["GET", "POST"])
def client_detail(request, pk):
    client = api_client_service.get_for_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    posted = {
        "code": client.code,
        "name": client.name,
        "description": client.description,
        "environment": client.environment,
        "scopes": list(client.scopes or []),
    }
    errors: dict = {}
    if request.method == "POST":
        posted = api_client_service.posted_from_request(request.POST)
        posted["environment"] = client.environment
        result = api_client_service.update_client(request.user, client, posted, request=request)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("platform_api:client_detail", pk=client.pk)
        errors = result.errors or {}
        messages.error(request, result.user_message)
        client = api_client_service.get_for_user(request.user, pk)
    webhook_posted = {
        "webhook_url": client.webhook_url,
        "webhook_enabled": client.webhook_enabled,
        "webhook_events": list(client.webhook_events or WEBHOOK_EVENTS),
    }
    webhook_errors: dict = {}
    bag = request.session.pop(WEBHOOK_SECRET_SESSION, None) or {}
    plaintext_webhook_secret = ""
    if str(bag.get("client_id")) == str(client.pk):
        plaintext_webhook_secret = bag.get("plaintext_webhook_secret") or ""
    return render(
        request,
        "platform_api/clients/detail.html",
        _ctx(
            client=client,
            posted=posted,
            errors=errors,
            webhook_posted=webhook_posted,
            webhook_errors=webhook_errors,
            webhook_deliveries=webhook_service.recent_for_client(client),
            plaintext_webhook_secret=plaintext_webhook_secret,
        ),
    )


@_us_view
@require_POST
def client_webhook(request, pk):
    client = api_client_service.get_for_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    posted = webhook_service.posted_from_request(request.POST)
    result = webhook_service.update_webhook(request.user, client, posted, request=request)
    if result.ok:
        secret = result.payload.get("plaintext_webhook_secret") or ""
        if secret:
            request.session[WEBHOOK_SECRET_SESSION] = {
                "client_id": str(client.pk),
                "plaintext_webhook_secret": secret,
            }
        messages.success(request, result.user_message)
        return redirect("platform_api:client_detail", pk=client.pk)
    messages.error(request, result.user_message)
    webhook_posted = posted
    webhook_errors = result.errors or {}
    posted_cfg = {
        "code": client.code,
        "name": client.name,
        "description": client.description,
        "environment": client.environment,
        "scopes": list(client.scopes or []),
    }
    return render(
        request,
        "platform_api/clients/detail.html",
        _ctx(
            client=client,
            posted=posted_cfg,
            errors={},
            webhook_posted=webhook_posted,
            webhook_errors=webhook_errors,
            webhook_deliveries=webhook_service.recent_for_client(client),
            plaintext_webhook_secret="",
        ),
    )


@_us_view
@require_POST
def client_rotate(request, pk):
    client = api_client_service.get_for_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    result = api_client_service.rotate_key(request.user, client, request=request)
    if not result.ok:
        messages.error(request, result.user_message)
        return redirect("platform_api:client_detail", pk=pk)
    request.session[REVEAL_SESSION] = {
        "client_id": str(result.payload["client"].pk),
        "plaintext_key": result.payload["plaintext_key"],
    }
    messages.success(request, result.user_message)
    return redirect("platform_api:client_reveal", pk=pk)


@_us_view
@require_POST
def client_revoke(request, pk):
    client = api_client_service.get_for_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    result = api_client_service.revoke_client(request.user, client, request=request)
    if result.ok:
        messages.success(request, result.user_message)
    else:
        messages.error(request, result.user_message)
    return redirect("platform_api:client_detail", pk=pk)


@_us_view
def audit_list(request):
    action = (request.GET.get("action") or "").strip()
    events, stats = client_audit_service.list_for_user(request.user, action=action)
    return render(
        request,
        "platform_api/audit/list.html",
        _ctx(
            app_nav_active="platform_api_audit",
            events=events,
            stats=stats,
            action_filter=action,
            action_choices=client_audit_service.action_choices(),
        ),
    )


@_us_view
def audit_list_help(request):
    return render(
        request,
        "platform_api/audit/list_help.html",
        _ctx(
            app_nav_active="platform_api_audit",
            action_choices=client_audit_service.action_choices(),
        ),
    )


@_us_view
def audit_event(request, pk):
    event = client_audit_service.get_event_for_user(request.user, pk)
    if event is None:
        messages.error(request, client_audit_service.MSG_EVENT_NOT_FOUND)
        return redirect("platform_api:audit_list")
    return render(
        request,
        "platform_api/audit/event.html",
        _ctx(app_nav_active="platform_api_audit", event=event),
    )


@_us_view
def audit_event_help(request, pk):
    event = client_audit_service.get_event_for_user(request.user, pk)
    if event is None:
        messages.error(request, client_audit_service.MSG_EVENT_NOT_FOUND)
        return redirect("platform_api:audit_list")
    return render(
        request,
        "platform_api/audit/event_help.html",
        _ctx(app_nav_active="platform_api_audit", event=event),
    )


@_us_view
def client_audit(request, pk):
    client, events, stats = client_audit_service.list_for_client_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    return render(
        request,
        "platform_api/audit/client.html",
        _ctx(client=client, events=events, stats=stats),
    )


@_us_view
def client_audit_help(request, pk):
    client, events, _stats = client_audit_service.list_for_client_user(request.user, pk)
    if client is None:
        messages.error(request, api_client_service.MSG_NOT_FOUND)
        return redirect("platform_api:client_list")
    return render(
        request,
        "platform_api/audit/client_help.html",
        _ctx(client=client, events=events),
    )


@_us_view
@require_http_methods(["GET", "POST"])
def security_policy(request):
    policy = process_security_service.get_policy_for_user(request.user)
    if policy is None:
        messages.error(request, process_security_service.MSG_US_ONLY)
        return redirect("platform_api:client_list")
    posted = process_security_service.default_posted(policy)
    errors: dict = {}
    if request.method == "POST":
        posted = process_security_service.posted_from_request(request.POST)
        result = process_security_service.update_policy(request.user, posted)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("platform_api:security_policy")
        errors = result.errors or {}
        messages.error(request, result.user_message)
        posted = {
            **process_security_service.default_posted(policy),
            **posted,
            "allowed_extensions": " ".join(posted.get("allowed_extensions") or []),
            "webhook_host_allowlist": "\n".join(posted.get("webhook_host_allowlist") or []),
        }
    return render(
        request,
        "platform_api/security/policy.html",
        _ctx(
            app_nav_active="platform_api_security",
            policy=policy,
            posted=posted,
            errors=errors,
        ),
    )


@_us_view
def security_policy_help(request):
    return render(
        request,
        "platform_api/security/policy_help.html",
        _ctx(
            app_nav_active="platform_api_security",
            policy=process_security_service.get_policy_for_user(request.user),
            default_max_mb=DEFAULT_MAX_UPLOAD_BYTES // (1024 * 1024),
            default_rate=DEFAULT_RATE_PER_MINUTE,
            default_ttl=DEFAULT_ARTIFACT_TTL_HOURS,
            default_extensions=" ".join(DEFAULT_ALLOWED_EXTENSIONS),
        ),
    )


@_us_view
def contract_guide(request):
    return render(
        request,
        "platform_api/contract/guide.html",
        _ctx(
            app_nav_active="platform_api_contract",
            catalog=contract_service.catalog(),
        ),
    )


@_us_view
def contract_guide_help(request):
    return render(
        request,
        "platform_api/contract/guide_help.html",
        _ctx(
            app_nav_active="platform_api_contract",
            catalog=contract_service.catalog(),
        ),
    )


@_us_view
def openapi_guide(request):
    return render(
        request,
        "platform_api/openapi/guide.html",
        _ctx(
            app_nav_active="platform_api_openapi",
            catalog=openapi_service.catalog(),
        ),
    )


@_us_view
def openapi_guide_help(request):
    return render(
        request,
        "platform_api/openapi/guide_help.html",
        _ctx(
            app_nav_active="platform_api_openapi",
            catalog=openapi_service.catalog(),
        ),
    )


@_us_view
def integration_guide(request):
    return render(
        request,
        "platform_api/integration/guide.html",
        _ctx(
            app_nav_active="platform_api_integration",
            catalog=integration_service.catalog(),
        ),
    )


@_us_view
def integration_guide_help(request):
    return render(
        request,
        "platform_api/integration/guide_help.html",
        _ctx(
            app_nav_active="platform_api_integration",
            catalog=integration_service.catalog(),
        ),
    )
