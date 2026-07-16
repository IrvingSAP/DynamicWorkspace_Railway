import logging
import re

from django.apps import apps as django_apps
from django.db import IntegrityError, transaction

from apps.accounts.models import UserProfile
from apps.company.models import Company
from apps.core.services.operation_result import OperationResult

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def queryset():
    return Company.objects.select_related("created_by", "updated_by")


def list_with_stats():
    companies = list(queryset())
    total = len(companies)
    active = sum(1 for company in companies if company.is_active)
    return companies, {
        "total": total,
        "active": active,
        "inactive": total - active,
    }


def _optional_model(app_label: str, model_name: str):
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None


def get_related_counts(company: Company) -> dict:
    users_count = UserProfile.objects.filter(company=company).count()

    projects_count = 0
    Project = _optional_model("projects", "Project")
    if Project is not None:
        projects_count = Project.objects.filter(company=company).count()

    subscription_label = "Sin suscripción"
    subscription_active = False
    Subscription = _optional_model("billing", "Subscription")
    if Subscription is not None:
        try:
            sub = Subscription.objects.select_related("plan").get(company=company)
            subscription_active = sub.status == "active"
            plan_name = sub.plan.name if sub.plan_id else "—"
            subscription_label = f"{plan_name} ({sub.get_status_display() if hasattr(sub, 'get_status_display') else sub.status})"
        except Subscription.DoesNotExist:
            pass

    return {
        "users_count": users_count,
        "projects_count": projects_count,
        "subscription_label": subscription_label,
        "subscription_active": subscription_active,
        "has_dependencies": users_count > 0 or projects_count > 0 or subscription_active,
    }


def get_detail_context(company: Company) -> dict:
    counts = get_related_counts(company)
    subscription_summary = "Sin suscripción"
    subscription_until = "—"

    Subscription = _optional_model("billing", "Subscription")
    if Subscription is not None:
        try:
            sub = Subscription.objects.select_related("plan").get(company=company)
            subscription_summary = sub.plan.name if sub.plan_id else "Plan"
            subscription_until = sub.end_date.strftime("%d/%m/%Y") if sub.end_date else "—"
        except Subscription.DoesNotExist:
            pass

    return {
        **counts,
        "subscription_summary": subscription_summary,
        "subscription_until": subscription_until,
    }


def get_account_context(company: Company) -> dict:
    """Datos de cuenta cliente (US): compañía y relaciones de negocio."""
    counts = get_related_counts(company)
    subscription_info = {
        "has_subscription": False,
        "plan_name": "Sin plan",
        "plan_code": "—",
        "status_label": "Sin suscripción",
        "status_code": "",
        "start_date": None,
        "end_date": None,
        "auto_renew": False,
        "contacts": [],
    }

    Subscription = _optional_model("billing", "Subscription")
    if Subscription is not None:
        try:
            sub = Subscription.objects.select_related("plan").prefetch_related(
                "contacts",
            ).get(company=company)
            subscription_info = {
                "has_subscription": True,
                "plan_name": sub.plan.name,
                "plan_code": sub.plan.code,
                "status_label": sub.get_status_display(),
                "status_code": sub.status,
                "start_date": sub.start_date,
                "end_date": sub.end_date,
                "auto_renew": sub.auto_renew,
                "contacts": list(sub.contacts.all()),
            }
        except Subscription.DoesNotExist:
            pass

    users_uf = UserProfile.objects.filter(
        company=company,
        user_type=UserProfile.USER_FINAL,
    ).count()
    users_us = UserProfile.objects.filter(
        company=company,
        user_type=UserProfile.USER_SYSTEM,
    ).count()

    return {
        "users_total": counts["users_count"],
        "users_uf": users_uf,
        "users_us": users_us,
        "projects_count": counts["projects_count"],
        "subscription": subscription_info,
    }


def posted_from_request(post, files=None, company: Company | None = None) -> dict:
    data = {
        "name_short": post.get("name_short", "").strip(),
        "name_long": post.get("name_long", "").strip(),
        "tax_id": post.get("tax_id", "").strip(),
        "address": post.get("address", "").strip(),
        "phone": post.get("phone", "").strip(),
        "email": post.get("email", "").strip(),
        "is_active": post.get("is_active") == "1",
    }
    if files and files.get("logo"):
        data["logo"] = files["logo"]
        data["logo_filename"] = files["logo"].name
    elif company is not None:
        data["logo"] = None
    return data


def default_posted(company: Company | None = None) -> dict:
    if company is None:
        return {
            "name_short": "",
            "name_long": "",
            "tax_id": "",
            "address": "",
            "phone": "",
            "email": "",
            "is_active": True,
        }
    return {
        "name_short": company.name_short,
        "name_long": company.name_long,
        "tax_id": company.tax_id,
        "address": company.address,
        "phone": company.phone,
        "email": company.email,
        "is_active": company.is_active,
    }


def validate_company_data(data: dict, company: Company | None = None) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    name_short = data.get("name_short", "").strip()
    if not name_short:
        errors.setdefault("name_short", []).append("Ingrese el código o sigla.")
    elif len(name_short) > 15:
        errors.setdefault("name_short", []).append("Máximo 15 caracteres.")
    elif not re.match(r"^[A-Za-z0-9._-]+$", name_short):
        errors.setdefault("name_short", []).append(
            "Use solo letras, números, punto, guion o guion bajo."
        )
    else:
        qs = Company.objects.filter(name_short__iexact=name_short)
        if company is not None:
            qs = qs.exclude(pk=company.pk)
        if qs.exists():
            errors.setdefault("name_short", []).append(
                "Ya existe una compañía con este código."
            )

    name_long = data.get("name_long", "").strip()
    if not name_long:
        errors.setdefault("name_long", []).append("Ingrese el nombre completo.")
    elif len(name_long) > 150:
        errors.setdefault("name_long", []).append("Máximo 150 caracteres.")

    tax_id = data.get("tax_id", "").strip()
    if len(tax_id) > 50:
        errors.setdefault("tax_id", []).append("Máximo 50 caracteres.")

    address = data.get("address", "").strip()
    if len(address) > 255:
        errors.setdefault("address", []).append("Máximo 255 caracteres.")

    phone = data.get("phone", "").strip()
    if len(phone) > 50:
        errors.setdefault("phone", []).append("Máximo 50 caracteres.")

    email = data.get("email", "").strip()
    if email and not EMAIL_RE.match(email):
        errors.setdefault("email", []).append("Ingrese un correo electrónico válido.")
    elif len(email) > 254:
        errors.setdefault("email", []).append("El correo es demasiado largo.")

    return errors


def create_company(user, data: dict) -> OperationResult:
    errors = validate_company_data(data)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    try:
        with transaction.atomic():
            company = Company(
                name_short=data["name_short"],
                name_long=data["name_long"],
                tax_id=data.get("tax_id", ""),
                address=data.get("address", ""),
                phone=data.get("phone", ""),
                email=data.get("email", ""),
                is_active=data.get("is_active", True),
                created_by=user,
                updated_by=user,
            )
            if data.get("logo"):
                company.logo = data["logo"]
            company.save()
    except IntegrityError:
        logger.exception("create_company IntegrityError name_short=%s", data.get("name_short"))
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"name_short": ["Ya existe una compañía con este código."]},
        )
    except Exception:
        logger.exception("create_company unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Compañía creada correctamente.",
        company=company,
    )


def update_company(user, company: Company, data: dict) -> OperationResult:
    errors = validate_company_data(data, company=company)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    try:
        with transaction.atomic():
            company.name_short = data["name_short"]
            company.name_long = data["name_long"]
            company.tax_id = data.get("tax_id", "")
            company.address = data.get("address", "")
            company.phone = data.get("phone", "")
            company.email = data.get("email", "")
            company.is_active = data.get("is_active", False)
            if data.get("logo"):
                company.logo = data["logo"]
            company.updated_by = user
            company.save()
    except IntegrityError:
        logger.exception("update_company IntegrityError pk=%s", company.pk)
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"name_short": ["Ya existe una compañía con este código."]},
        )
    except Exception:
        logger.exception("update_company unexpected pk=%s", company.pk)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Compañía actualizada correctamente.",
        company=company,
    )


def delete_company(company: Company) -> OperationResult:
    counts = get_related_counts(company)
    if counts["users_count"] > 0 or counts["projects_count"] > 0 or counts["subscription_active"]:
        return OperationResult.failure(
            "protected_delete",
            "No se puede eliminar la compañía: existen usuarios, proyectos o una suscripción activa.",
        )

    try:
        company.delete()
    except Exception:
        logger.exception("delete_company unexpected pk=%s", company.pk)
        return OperationResult.failure(
            "protected_delete",
            "No se puede eliminar la compañía: existen usuarios, proyectos o una suscripción activa.",
        )

    return OperationResult.success(
        user_message="Compañía eliminada correctamente.",
    )
