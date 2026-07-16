import logging
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.billing.models import Payment, Subscription
from apps.core.services.operation_result import OperationResult

logger = logging.getLogger(__name__)


def queryset():
    return Payment.objects.select_related(
        "subscription__company",
        "subscription__plan",
        "created_by",
    )


def list_with_stats():
    payments = list(queryset())
    total = len(payments)
    amount_total = sum(payment.amount for payment in payments)
    return payments, {
        "total": total,
        "amount_total": amount_total,
    }


def eligible_subscriptions():
    return Subscription.objects.select_related("company", "plan").filter(
        status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_PENDING],
    ).order_by("company__name_short")


def posted_from_request(post) -> dict:
    amount_raw = post.get("amount", "").strip()
    amount = None
    if amount_raw:
        try:
            amount = Decimal(amount_raw.replace(",", "."))
        except InvalidOperation:
            amount = amount_raw

    paid_at_raw = post.get("paid_at", "").strip()
    return {
        "subscription_id": post.get("subscription_id", "").strip(),
        "amount": amount,
        "method": post.get("method", "").strip(),
        "reference": post.get("reference", "").strip(),
        "paid_at": paid_at_raw,
    }


def default_posted() -> dict:
    now = timezone.localtime()
    return {
        "subscription_id": "",
        "amount": "",
        "method": Payment.METHOD_MANUAL,
        "reference": "",
        "paid_at": now.strftime("%Y-%m-%dT%H:%M"),
    }


def validate_payment_data(data: dict) -> tuple[dict[str, list[str]], dict]:
    errors: dict[str, list[str]] = {}
    validated: dict = {}

    subscription_id = data.get("subscription_id", "").strip()
    subscription = None
    if not subscription_id:
        errors.setdefault("subscription_id", []).append("Seleccione una suscripción.")
    else:
        try:
            sub_uuid = uuid.UUID(subscription_id)
        except ValueError:
            errors.setdefault("subscription_id", []).append("Suscripción no válida.")
        else:
            try:
                subscription = Subscription.objects.select_related("company").get(
                    pk=sub_uuid,
                )
            except Subscription.DoesNotExist:
                errors.setdefault("subscription_id", []).append(
                    "Suscripción no encontrada.",
                )
            else:
                if subscription.status not in (
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_PENDING,
                ):
                    errors.setdefault("subscription_id", []).append(
                        "Solo se registran pagos en suscripciones activas o pendientes.",
                    )

    amount = data.get("amount")
    if amount is None or amount == "":
        errors.setdefault("amount", []).append("Ingrese el monto.")
    elif not isinstance(amount, Decimal):
        errors.setdefault("amount", []).append("Ingrese un monto numérico válido.")
    elif amount < Decimal("0.01"):
        errors.setdefault("amount", []).append("El monto mínimo es 0.01.")

    method = data.get("method", "").strip()
    valid_methods = {choice[0] for choice in Payment.METHOD_CHOICES}
    if method not in valid_methods:
        errors.setdefault("method", []).append("Seleccione un método de pago.")

    paid_at_raw = data.get("paid_at", "").strip()
    if not paid_at_raw:
        errors.setdefault("paid_at", []).append("Ingrese la fecha del pago.")
    else:
        parsed = None
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(paid_at_raw, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            errors.setdefault("paid_at", []).append("Fecha de pago no válida.")
        else:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            validated["paid_at"] = parsed

    validated["subscription"] = subscription
    return errors, validated


def create_payment(user, data: dict) -> OperationResult:
    errors, validated = validate_payment_data(data)
    if errors:
        user_message = "Revise los campos marcados."
        if any(
            "Solo se registran pagos" in msg
            for msgs in errors.values()
            for msg in msgs
        ):
            user_message = (
                "Solo se registran pagos en suscripciones activas o pendientes."
            )
        return OperationResult.failure(
            "validation_form",
            user_message,
            errors=errors,
        )

    subscription = validated["subscription"]
    try:
        with transaction.atomic():
            payment = Payment.objects.create(
                subscription=subscription,
                amount=data["amount"],
                method=data["method"],
                reference=data.get("reference", ""),
                paid_at=validated["paid_at"],
                created_by=user,
            )
    except Exception:
        logger.exception("Error al registrar pago")
        return OperationResult.failure(
            "integrity_error",
            "No se pudo registrar el pago.",
        )

    return OperationResult.success(
        user_message="Pago registrado correctamente.",
        payment=payment,
    )
