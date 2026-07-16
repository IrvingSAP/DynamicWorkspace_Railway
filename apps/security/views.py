from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.core.decorators import pending_security_user_required
from apps.security.services.email_confirmation import (
    mask_email,
    send_confirmation_code,
    verify_email_code,
)
from apps.security.services.login_flow import authenticate_credentials
from apps.security.services.profile_routing import (
    post_login_redirect_name,
    wizard_step_state,
)
from apps.security.services.security_session import (
    clear_pending_user,
    get_pending_user,
    set_pending_user,
)
from apps.security.services.totp_reset import reset_two_factor
from apps.security.services.totp_utils import (
    ensure_totp_secret,
    format_secret_for_display,
    generate_qr_data_uri,
    get_provisioning_uri,
    verify_totp_code,
)


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.is_security_complete:
                return redirect("dashboard:home")
        except Exception:
            pass

    posted = {"username": "", "password": ""}
    errors: dict[str, list[str]] = {}

    if request.method == "POST":
        posted = {
            "username": request.POST.get("username", ""),
            "password": request.POST.get("password", ""),
        }
        result = authenticate_credentials(posted["username"], posted["password"])
        if result.ok:
            user = result.payload["user"]
            set_pending_user(request, user.id)
            return redirect(result.payload["next_step"])
        if result.errors:
            errors = result.errors
        messages.error(request, result.user_message)

    return render(
        request,
        "security/login.html",
        {"posted": posted, "errors": errors},
    )


def cancel_view(request):
    clear_pending_user(request)
    logout(request)
    messages.info(request, "Ingreso cancelado.")
    return redirect("security:login")


@pending_security_user_required
@require_http_methods(["GET", "POST"])
def email_code_view(request):
    profile = request.security_profile

    if profile.email_confirmed:
        return redirect("security:totp_setup")

    if request.method == "POST":
        if request.POST.get("action") == "resend":
            result = send_confirmation_code(profile)
            if result.ok:
                messages.success(request, "Código reenviado. Revisa tu correo.")
            else:
                messages.error(request, result.user_message)
            return redirect("security:email_code")

        posted = {"email_code": request.POST.get("email_code", "")}
        result = verify_email_code(profile, posted["email_code"])
        if result.ok:
            return redirect("security:totp_setup")
        errors = result.errors or {}
        messages.error(request, result.user_message)
        context = {
            "wizard": wizard_step_state(profile),
            "masked_email": mask_email(profile.user.email),
            "posted": posted,
            "errors": errors,
        }
        return render(request, "security/email_code.html", context)

    code_missing = not profile.email_confirm_code
    code_expired = (
        profile.email_confirm_exp is None
        or profile.email_confirm_exp < timezone.now()
    )
    if code_missing or code_expired:
        send_result = send_confirmation_code(profile)
        if not send_result.ok:
            messages.error(request, send_result.user_message)

    context = {
        "wizard": wizard_step_state(profile),
        "masked_email": mask_email(profile.user.email),
        "posted": {"email_code": ""},
        "errors": {},
    }
    return render(request, "security/email_code.html", context)


@pending_security_user_required
@require_http_methods(["GET"])
def totp_setup_view(request):
    profile = request.security_profile

    if not profile.email_confirmed:
        return redirect("security:email_code")

    if profile.is_security_complete:
        return redirect("security:totp")

    profile = ensure_totp_secret(profile)
    uri = get_provisioning_uri(profile)
    context = {
        "wizard": wizard_step_state(profile),
        "qr_data_uri": generate_qr_data_uri(uri),
        "manual_secret": format_secret_for_display(profile.totp_secret),
    }
    return render(request, "security/totp_setup.html", context)


@pending_security_user_required
@require_http_methods(["GET", "POST"])
def totp_view(request):
    profile = request.security_profile

    if not profile.email_confirmed:
        return redirect("security:email_code")

    if not profile.totp_secret and not profile.is_security_complete:
        return redirect("security:totp_setup")

    posted = {"totp_code": ""}
    errors: dict[str, list[str]] = {}

    if request.method == "POST":
        posted["totp_code"] = request.POST.get("totp_code", "")
        result = verify_totp_code(profile, posted["totp_code"])
        if result.ok:
            user = request.security_user
            clear_pending_user(request)
            login(request, user)
            messages.success(request, "Acceso verificado correctamente.")
            return redirect(post_login_redirect_name(profile))
        if result.errors:
            errors = result.errors
        messages.error(request, result.user_message)

    context = {
        "wizard": wizard_step_state(profile),
        "posted": posted,
        "errors": errors,
        "show_reset_link": profile.is_security_complete or profile.email_confirmed,
    }
    return render(request, "security/totp.html", context)


@pending_security_user_required
@require_http_methods(["GET", "POST"])
def actualizar_2fa_view(request):
    profile = request.security_profile

    if request.method == "POST":
        result = reset_two_factor(profile)
        if result.ok:
            messages.warning(
                request,
                "Tu autenticación 2FA fue reiniciada. Verifica tu correo para continuar.",
            )
            return redirect("security:email_code")
        messages.error(request, result.user_message)

    return render(request, "security/actualizar_2fa.html")


@require_http_methods(["POST", "GET"])
def logout_view(request):
    clear_pending_user(request)
    logout(request)
    return redirect("security:login")
