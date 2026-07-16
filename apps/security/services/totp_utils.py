import base64
import io
import logging

import pyotp
import qrcode

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.security.constants import TOTP_ISSUER

logger = logging.getLogger(__name__)


def generate_secret() -> str:
    return pyotp.random_base32()


def format_secret_for_display(secret: str) -> str:
    secret = (secret or "").replace(" ", "")
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


def get_provisioning_uri(profile: UserProfile) -> str:
    totp = pyotp.TOTP(profile.totp_secret)
    return totp.provisioning_uri(
        name=profile.user.email or profile.user.username,
        issuer_name=TOTP_ISSUER,
    )


def generate_qr_data_uri(uri: str) -> str:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def ensure_totp_secret(profile: UserProfile) -> UserProfile:
    if not profile.totp_secret:
        profile.totp_secret = generate_secret()
        profile.save(update_fields=["totp_secret", "updated_at"])
    return profile


def verify_totp_code(profile: UserProfile, code: str) -> OperationResult:
    code = (code or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        return OperationResult.failure(
            "validation_form",
            "Código de autenticación incorrecto.",
            errors={"totp_code": ["Ingrese el código de 6 dígitos."]},
        )

    if not profile.totp_secret:
        return OperationResult.failure(
            "business_blocked",
            "Debes configurar tu autenticador antes de continuar.",
        )

    totp = pyotp.TOTP(profile.totp_secret)
    if not totp.verify(code, valid_window=1):
        return OperationResult.failure(
            "validation_form",
            "Código de autenticación incorrecto.",
            errors={"totp_code": ["Código de autenticación incorrecto."]},
        )

    if not profile.tfa_verified:
        profile.tfa_verified = True
        profile.save(update_fields=["tfa_verified", "updated_at"])

    return OperationResult.success()
