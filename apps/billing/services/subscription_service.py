import logging
import re
import uuid
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing.models import Plan, Subscription, SubscriptionContact
from apps.company.models import Company
from apps.core.services.operation_result import OperationResult

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_CONTACTS = 3


def queryset():
    return Subscription.objects.select_related(
        "company",
        "plan",
        "created_by",
        "updated_by",
    ).prefetch_related("contacts")


def list_with_stats():
    subscriptions = list(queryset())
    total = len(subscriptions)
    active = sum(1 for sub in subscriptions if sub.status == Subscription.STATUS_ACTIVE)
    pending = sum(1 for sub in subscriptions if sub.status == Subscription.STATUS_PENDING)
    expired = sum(1 for sub in subscriptions if sub.status == Subscription.STATUS_EXPIRED)
    return subscriptions, {
        "total": total,
        "active": active,
        "pending": pending,
        "expired": expired,
    }


def companies_without_subscription():
    subscribed_ids = Subscription.objects.values_list("company_id", flat=True)
    return Company.objects.filter(is_active=True).exclude(
        pk__in=subscribed_ids,
    ).order_by("name_short")


def active_plans():
    return Plan.objects.filter(is_active=True).order_by("code")


def contacts_from_request(post) -> list[dict]:
    contacts = []
    for index in range(1, MAX_CONTACTS + 1):
        name = post.get(f"contact_{index}_name", "").strip()
        email = post.get(f"contact_{index}_email", "").strip()
        phone = post.get(f"contact_{index}_phone", "").strip()
        role = post.get(f"contact_{index}_role", "").strip()
        if name or email or phone or role:
            contacts.append(
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                }
            )
    return contacts


def default_contacts_posted(subscription: Subscription | None = None) -> dict:
    posted = {}
    contacts = []
    if subscription is not None:
        contacts = list(subscription.contacts.all()[:MAX_CONTACTS])
    for index in range(1, MAX_CONTACTS + 1):
        contact = contacts[index - 1] if index - 1 < len(contacts) else None
        posted[f"contact_{index}_name"] = contact.name if contact else ""
        posted[f"contact_{index}_email"] = contact.email if contact else ""
        posted[f"contact_{index}_phone"] = contact.phone if contact else ""
        posted[f"contact_{index}_role"] = contact.role if contact else ""
    return posted


def posted_from_request(post, subscription: Subscription | None = None) -> dict:
    data = {
        "company_id": post.get("company_id", "").strip(),
        "plan_id": post.get("plan_id", "").strip(),
        "start_date": post.get("start_date", "").strip(),
        "end_date": post.get("end_date", "").strip(),
        "status": post.get("status", "").strip(),
        "auto_renew": post.get("auto_renew") == "1",
    }
    for index in range(1, MAX_CONTACTS + 1):
        data[f"contact_{index}_name"] = post.get(f"contact_{index}_name", "").strip()
        data[f"contact_{index}_email"] = post.get(f"contact_{index}_email", "").strip()
        data[f"contact_{index}_phone"] = post.get(f"contact_{index}_phone", "").strip()
        data[f"contact_{index}_role"] = post.get(f"contact_{index}_role", "").strip()
    if subscription is not None:
        data["company_id"] = str(subscription.company_id)
    return data


def default_posted(subscription: Subscription | None = None) -> dict:
    if subscription is None:
        return {
            "company_id": "",
            "plan_id": "",
            "start_date": "",
            "end_date": "",
            "status": Subscription.STATUS_PENDING,
            "auto_renew": False,
            **default_contacts_posted(),
        }
    return {
        "company_id": str(subscription.company_id),
        "plan_id": str(subscription.plan_id),
        "start_date": subscription.start_date.isoformat(),
        "end_date": subscription.end_date.isoformat(),
        "status": subscription.status,
        "auto_renew": subscription.auto_renew,
        **default_contacts_posted(subscription),
    }


def _parse_date(value: str, field: str, errors: dict) -> None:
    if not value:
        errors.setdefault(field, []).append("Ingrese la fecha.")
        return
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        errors.setdefault(field, []).append("Fecha no válida.")


def _validate_contacts(data: dict) -> tuple[list[dict], dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    contacts = []
    for index in range(1, MAX_CONTACTS + 1):
        name = data.get(f"contact_{index}_name", "").strip()
        email = data.get(f"contact_{index}_email", "").strip()
        phone = data.get(f"contact_{index}_phone", "").strip()
        role = data.get(f"contact_{index}_role", "").strip()
        if not (name or email or phone or role):
            continue
        prefix = f"contact_{index}"
        if not name:
            errors.setdefault(f"{prefix}_name", []).append("Ingrese el nombre.")
        if not email:
            errors.setdefault(f"{prefix}_email", []).append("Ingrese el correo.")
        elif not EMAIL_RE.match(email):
            errors.setdefault(f"{prefix}_email", []).append("Correo no válido.")
        contacts.append(
            {
                "name": name,
                "email": email,
                "phone": phone,
                "role": role,
            }
        )

    if len(contacts) > MAX_CONTACTS:
        errors.setdefault("contacts", []).append(
            "Máximo 3 contactos de soporte por suscripción.",
        )

    emails = [contact["email"].lower() for contact in contacts if contact.get("email")]
    if len(emails) != len(set(emails)):
        errors.setdefault("contacts", []).append(
            "No repita el mismo correo en varios contactos.",
        )

    return contacts, errors


def validate_subscription_data(
    data: dict,
    subscription: Subscription | None = None,
) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    company_id = data.get("company_id", "").strip()
    if subscription is None:
        if not company_id:
            errors.setdefault("company_id", []).append("Seleccione una compañía.")
        else:
            try:
                company_uuid = uuid.UUID(company_id)
            except ValueError:
                errors.setdefault("company_id", []).append("Compañía no válida.")
            else:
                if not Company.objects.filter(pk=company_uuid, is_active=True).exists():
                    errors.setdefault("company_id", []).append("Compañía no encontrada.")
                elif Subscription.objects.filter(company_id=company_uuid).exists():
                    errors.setdefault("company_id", []).append(
                        "Esta compañía ya tiene una suscripción asignada.",
                    )

    plan_id = data.get("plan_id", "").strip()
    if not plan_id:
        errors.setdefault("plan_id", []).append("Seleccione un plan.")
    else:
        try:
            plan_uuid = uuid.UUID(plan_id)
        except ValueError:
            errors.setdefault("plan_id", []).append("Plan no válido.")
        else:
            if not Plan.objects.filter(pk=plan_uuid).exists():
                errors.setdefault("plan_id", []).append("Plan no encontrado.")

    _parse_date(data.get("start_date", ""), "start_date", errors)
    _parse_date(data.get("end_date", ""), "end_date", errors)

    if (
        "start_date" not in errors
        and "end_date" not in errors
        and data.get("start_date")
        and data.get("end_date")
    ):
        start = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        end = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
        if end < start:
            errors.setdefault("end_date", []).append(
                "La fecha fin debe ser posterior o igual al inicio.",
            )

    status = data.get("status", "").strip()
    valid_status = {choice[0] for choice in Subscription.STATUS_CHOICES}
    if status not in valid_status:
        errors.setdefault("status", []).append("Seleccione un estado válido.")

    contacts, contact_errors = _validate_contacts(data)
    errors.update(contact_errors)
    data["_contacts"] = contacts
    return errors


def _save_contacts(subscription: Subscription, contacts: list[dict]) -> None:
    subscription.contacts.all().delete()
    for contact_data in contacts:
        contact = SubscriptionContact(
            subscription=subscription,
            name=contact_data["name"],
            email=contact_data["email"],
            phone=contact_data.get("phone", ""),
            role=contact_data.get("role", ""),
        )
        contact.full_clean()
        contact.save()


def create_subscription(user, data: dict) -> OperationResult:
    errors = validate_subscription_data(data)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los campos marcados.",
            errors=errors,
        )

    contacts = data.get("_contacts", [])
    start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    try:
        with transaction.atomic():
            subscription = Subscription(
                company_id=data["company_id"],
                plan_id=data["plan_id"],
                start_date=start_date,
                end_date=end_date,
                status=data["status"],
                auto_renew=data.get("auto_renew", False),
                created_by=user,
                updated_by=user,
            )
            subscription.full_clean()
            subscription.save()
            if contacts:
                _save_contacts(subscription, contacts)
    except IntegrityError:
        logger.exception("Error al crear suscripción")
        return OperationResult.failure(
            "integrity_error",
            "Esta compañía ya tiene una suscripción asignada.",
        )

    return OperationResult.success(
        user_message="Suscripción registrada correctamente.",
        subscription=subscription,
    )


def update_subscription(
    user,
    subscription: Subscription,
    data: dict,
) -> OperationResult:
    errors = validate_subscription_data(data, subscription=subscription)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los campos marcados.",
            errors=errors,
        )

    contacts = data.get("_contacts", [])
    subscription.plan_id = data["plan_id"]
    subscription.start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    subscription.end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    subscription.status = data["status"]
    subscription.auto_renew = data.get("auto_renew", False)
    subscription.updated_by = user

    try:
        with transaction.atomic():
            subscription.full_clean()
            subscription.save()
            _save_contacts(subscription, contacts)
    except IntegrityError:
        logger.exception("Error al actualizar suscripción %s", subscription.pk)
        return OperationResult.failure(
            "integrity_error",
            "No se pudo actualizar la suscripción.",
        )

    return OperationResult.success(
        user_message="Suscripción registrada correctamente.",
        subscription=subscription,
    )


def delete_subscription(subscription: Subscription) -> OperationResult:
    company_pk = subscription.company_id
    subscription.delete()
    return OperationResult.success(
        user_message="Suscripción eliminada correctamente.",
        company_pk=company_pk,
    )


def get_detail_context(subscription: Subscription) -> dict:
    from apps.billing.services.license_service import validate_license

    license_info = validate_license(subscription)
    return {
        "license_info": license_info,
        "contacts": list(subscription.contacts.all()),
        "payments": list(
            subscription.payments.select_related("created_by").order_by("-paid_at")[:10]
        ),
        "payments_count": subscription.payments.count(),
    }
