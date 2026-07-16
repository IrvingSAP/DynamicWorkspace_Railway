import hashlib
import hmac

from django.conf import settings
from django.utils import timezone

from apps.billing.models import Subscription
from apps.core.services.operation_result import OperationResult


def get_license_secret() -> str:
    return getattr(settings, "LICENSE_SECRET_KEY", settings.SECRET_KEY)


def generate_signature(start_date, end_date, secret: str | None = None) -> str:
    key = secret or get_license_secret()
    message = f"{start_date.isoformat()}|{end_date.isoformat()}"
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def is_signature_valid(subscription: Subscription) -> bool:
    expected = generate_signature(subscription.start_date, subscription.end_date)
    stored = subscription.integrity_signature or ""
    return bool(stored) and hmac.compare_digest(stored, expected)


def validate_license(subscription: Subscription) -> dict:
    today = timezone.localdate()
    return {
        "signature_valid": is_signature_valid(subscription),
        "is_expired": subscription.end_date < today,
        "status": subscription.status,
        "contacts": list(subscription.contacts.all()),
    }


def evaluate_subscription_access(subscription: Subscription) -> OperationResult:
    if not is_signature_valid(subscription):
        return OperationResult.failure(
            "invalid_signature",
            "La licencia de su compañía no es válida. Contacte al administrador.",
        )

    today = timezone.localdate()
    if subscription.end_date < today:
        return OperationResult.failure(
            "subscription_expired",
            "La suscripción de su compañía ha vencido.",
        )

    if subscription.status != Subscription.STATUS_ACTIVE:
        return OperationResult.failure(
            "subscription_inactive",
            "La suscripción de su compañía no está activa.",
        )

    return OperationResult.success()
