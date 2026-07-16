import logging
import secrets
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.core.services.email_delivery import send_email
from apps.core.services.operation_result import OperationResult
from apps.security.constants import (
    EMAIL_CODE_EXPIRY_MINUTES,
    EMAIL_SUBJECT,
    RESEND_COOLDOWN_SECONDS,
)

logger = logging.getLogger(__name__)


def mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _can_resend(profile: UserProfile) -> bool:
    if not profile.email_confirm_exp:
        return True
    last_sent = profile.email_confirm_exp - timedelta(minutes=EMAIL_CODE_EXPIRY_MINUTES)
    return (timezone.now() - last_sent).total_seconds() >= RESEND_COOLDOWN_SECONDS


def send_confirmation_code(profile: UserProfile) -> OperationResult:
    user = profile.user
    if not user.email:
        return OperationResult.failure(
            "business_blocked",
            "Tu cuenta no tiene correo configurado. Contacta al administrador.",
        )

    if not _can_resend(profile):
        return OperationResult.failure(
            "business_blocked",
            "Espera un momento antes de solicitar otro código.",
        )

    code = _generate_code()
    profile.email_confirm_code = code
    profile.email_confirm_exp = timezone.now() + timedelta(minutes=EMAIL_CODE_EXPIRY_MINUTES)
    profile.save(
        update_fields=["email_confirm_code", "email_confirm_exp", "updated_at"],
    )

    body = (
        f"Hola {user.get_full_name() or user.username},\n\n"
        f"Tu código de verificación DynamicWorkspace es: {code}\n\n"
        f"Este código vence en {EMAIL_CODE_EXPIRY_MINUTES} minutos.\n\n"
        "Si no solicitaste este código, ignora este mensaje."
    )
    mail_result = send_email(
        to=[user.email],
        subject=EMAIL_SUBJECT,
        body=body,
    )
    if not mail_result.ok:
        return mail_result

    return OperationResult.success(
        payload={"masked_email": mask_email(user.email)},
    )


def verify_email_code(profile: UserProfile, code: str) -> OperationResult:
    code = (code or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        return OperationResult.failure(
            "validation_form",
            "Código inválido o expirado.",
            errors={"email_code": ["Ingrese el código de 6 dígitos."]},
        )

    if (
        not profile.email_confirm_code
        or not profile.email_confirm_exp
        or profile.email_confirm_exp < timezone.now()
        or profile.email_confirm_code != code
    ):
        return OperationResult.failure(
            "validation_form",
            "Código inválido o expirado.",
            errors={"email_code": ["Código inválido o expirado."]},
        )

    profile.email_confirmed = True
    profile.email_confirm_code = None
    profile.email_confirm_exp = None
    profile.save(
        update_fields=[
            "email_confirmed",
            "email_confirm_code",
            "email_confirm_exp",
            "updated_at",
        ],
    )
    return OperationResult.success()
