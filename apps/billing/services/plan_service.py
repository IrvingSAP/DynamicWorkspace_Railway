import logging
import re
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError

from apps.billing.models import Plan
from apps.core.services.operation_result import OperationResult

logger = logging.getLogger(__name__)

CODE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def queryset():
    return Plan.objects.annotate(
        subscriptions_count=Count("subscriptions"),
    )


def list_with_stats():
    plans = list(queryset())
    total = len(plans)
    active = sum(1 for plan in plans if plan.is_active)
    subscriptions_total = sum(plan.subscriptions_count for plan in plans)
    return plans, {
        "total": total,
        "active": active,
        "inactive": total - active,
        "subscriptions_total": subscriptions_total,
    }


def posted_from_request(post, plan: Plan | None = None) -> dict:
    price_raw = post.get("price", "").strip()
    price = None
    if price_raw:
        try:
            price = Decimal(price_raw.replace(",", "."))
        except InvalidOperation:
            price = price_raw
    return {
        "code": post.get("code", "").strip().lower(),
        "name": post.get("name", "").strip(),
        "description": post.get("description", "").strip(),
        "billing_period": post.get("billing_period", "").strip(),
        "price": price,
        "is_active": post.get("is_active") == "1",
    }


def default_posted(plan: Plan | None = None) -> dict:
    if plan is None:
        return {
            "code": "",
            "name": "",
            "description": "",
            "billing_period": Plan.PERIOD_MONTHLY,
            "price": "",
            "is_active": True,
        }
    return {
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "billing_period": plan.billing_period,
        "price": plan.price if plan.price is not None else "",
        "is_active": plan.is_active,
    }


def validate_plan_data(data: dict, plan: Plan | None = None) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    code = data.get("code", "").strip().lower()
    if not code:
        errors.setdefault("code", []).append("Ingrese el código del plan.")
    elif len(code) > 50:
        errors.setdefault("code", []).append("Máximo 50 caracteres.")
    elif not CODE_RE.match(code):
        errors.setdefault("code", []).append(
            "Use solo minúsculas, números y guiones (slug)."
        )
    else:
        qs = Plan.objects.filter(code__iexact=code)
        if plan is not None:
            qs = qs.exclude(pk=plan.pk)
        if qs.exists():
            errors.setdefault("code", []).append("Ya existe un plan con este código.")

    name = data.get("name", "").strip()
    if not name:
        errors.setdefault("name", []).append("Ingrese el nombre visible.")
    elif len(name) > 100:
        errors.setdefault("name", []).append("Máximo 100 caracteres.")

    period = data.get("billing_period", "").strip()
    valid_periods = {choice[0] for choice in Plan.PERIOD_CHOICES}
    if period not in valid_periods:
        errors.setdefault("billing_period", []).append("Seleccione un periodo válido.")

    price = data.get("price")
    if price is not None and price != "" and not isinstance(price, Decimal):
        errors.setdefault("price", []).append("Ingrese un precio numérico válido.")
    elif isinstance(price, Decimal) and price < 0:
        errors.setdefault("price", []).append("El precio no puede ser negativo.")

    return errors


def create_plan(user, data: dict) -> OperationResult:
    errors = validate_plan_data(data)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los campos marcados.",
            errors=errors,
        )

    try:
        with transaction.atomic():
            plan = Plan.objects.create(
                code=data["code"],
                name=data["name"],
                description=data.get("description", ""),
                billing_period=data["billing_period"],
                price=data["price"] if data["price"] != "" else None,
                is_active=data.get("is_active", True),
            )
    except IntegrityError:
        logger.exception("Error al crear plan")
        return OperationResult.failure(
            "integrity_error",
            "No se pudo crear el plan. Verifique que el código sea único.",
        )

    return OperationResult.success(
        user_message="Plan creado correctamente.",
        plan=plan,
    )


def update_plan(user, plan: Plan, data: dict) -> OperationResult:
    errors = validate_plan_data(data, plan=plan)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los campos marcados.",
            errors=errors,
        )

    plan.code = data["code"]
    plan.name = data["name"]
    plan.description = data.get("description", "")
    plan.billing_period = data["billing_period"]
    plan.price = data["price"] if data["price"] != "" else None
    plan.is_active = data.get("is_active", True)

    try:
        plan.save()
    except IntegrityError:
        logger.exception("Error al actualizar plan %s", plan.pk)
        return OperationResult.failure(
            "integrity_error",
            "No se pudo actualizar el plan.",
        )

    return OperationResult.success(
        user_message="Plan actualizado correctamente.",
        plan=plan,
    )


def delete_plan(plan: Plan) -> OperationResult:
    if plan.subscriptions.exists():
        return OperationResult.failure(
            "protected",
            "No se puede eliminar el plan: tiene suscripciones asociadas.",
        )

    try:
        plan.delete()
    except ProtectedError:
        return OperationResult.failure(
            "protected",
            "No se puede eliminar el plan: tiene suscripciones asociadas.",
        )

    return OperationResult.success(user_message="Plan eliminado correctamente.")
