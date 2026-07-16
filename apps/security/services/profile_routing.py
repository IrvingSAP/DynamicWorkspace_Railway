from apps.accounts.models import UserProfile


def resolve_security_step_name(profile: UserProfile) -> str:
    if profile.is_security_complete:
        return "security:totp"
    if not profile.email_confirmed:
        return "security:email_code"
    if not profile.tfa_verified:
        if profile.totp_secret:
            return "security:totp"
        return "security:totp_setup"
    return "security:totp_setup"


def post_login_redirect_name(profile: UserProfile) -> str:
    if not profile.primer_acceso_completado:
        return "dashboard:bienvenida"
    return "dashboard:home"


def wizard_step_state(profile: UserProfile) -> dict[str, str]:
    if not profile.email_confirmed:
        return {"credentials": "done", "email": "active", "totp": ""}
    if not profile.tfa_verified:
        return {"credentials": "done", "email": "done", "totp": "active"}
    return {"credentials": "done", "email": "done", "totp": "active"}
