from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.security.services.email_confirmation import send_confirmation_code

_SECURITY_CYCLE_FIELDS = (
    "email_confirmed",
    "email_confirm_code",
    "email_confirm_exp",
    "totp_secret",
    "tfa_verified",
    "primer_acceso_completado",
    "locked_until",
    "last_totp_reset",
    "updated_at",
)


def reset_security_cycle(
    profile: UserProfile,
    *,
    record_reset_timestamp: bool = True,
) -> None:
    """Reinicia el ciclo de seguridad (correo, 2FA, bienvenida)."""
    profile.email_confirmed = False
    profile.email_confirm_code = None
    profile.email_confirm_exp = None
    profile.totp_secret = None
    profile.tfa_verified = False
    profile.primer_acceso_completado = False
    profile.locked_until = None
    if record_reset_timestamp:
        profile.last_totp_reset = timezone.now()
    profile.save(update_fields=list(_SECURITY_CYCLE_FIELDS))


def reset_two_factor(profile: UserProfile) -> OperationResult:
    reset_security_cycle(profile)
    return send_confirmation_code(profile)
