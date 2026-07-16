import logging
import re
import uuid

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from apps.accounts.models import UserProfile
from apps.company.models import Company
from apps.core.services.operation_result import OperationResult

logger = logging.getLogger(__name__)

User = get_user_model()

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9.@+-]+$")


def get_management_scope(actor_profile: UserProfile) -> dict:
    if actor_profile.user_type == UserProfile.USER_ADMIN:
        return {
            "actor_type": UserProfile.USER_ADMIN,
            "target_type": UserProfile.USER_SYSTEM,
            "page_eyebrow": "Administradores de compañía",
            "list_title": "Usuarios US",
            "list_description": (
                "User System por compañía. Solo puede crear y gestionar usuarios tipo US."
            ),
            "show_company_column": True,
            "show_company_picker": True,
            "fixed_company": None,
            "allowed_user_types": [UserProfile.USER_SYSTEM],
            "create_title": "Nuevo usuario US",
            "create_description": (
                "Crear User System y asignar compañía. "
                "El onboarding de seguridad ocurre en el primer login."
            ),
            "create_button": "Crear usuario US",
            "stats_total_label": "Total US",
            "stats_security_label": "Seguridad pendiente",
            "show_companies_stat": True,
            "target_badge_class": "user-type-badge--us",
            "detail_eyebrow": "User System",
        }

    return {
        "actor_type": UserProfile.USER_SYSTEM,
        "target_type": UserProfile.USER_FINAL,
        "page_eyebrow": "Usuarios finales",
        "list_title": "Usuarios UF",
        "list_description": (
            "User Final de tu compañía. Solo puede crear usuarios tipo UF."
        ),
        "show_company_column": False,
        "show_company_picker": False,
        "fixed_company": actor_profile.company,
        "allowed_user_types": [UserProfile.USER_FINAL],
        "create_title": "Nuevo usuario UF",
        "create_description": (
            f"Crear User Final en {actor_profile.company.name_long}. "
            "La compañía se asigna automáticamente."
        ),
        "create_button": "Crear usuario UF",
        "stats_total_label": "Total UF",
        "stats_security_label": "Onboarding pendiente",
        "show_companies_stat": False,
        "target_badge_class": "user-type-badge--uf",
        "detail_eyebrow": "User Final",
    }


def manageable_queryset(actor_profile: UserProfile):
    scope = get_management_scope(actor_profile)
    qs = UserProfile.objects.select_related(
        "user",
        "company",
        "created_by",
        "updated_by",
    ).filter(user_type=scope["target_type"])
    if actor_profile.user_type == UserProfile.USER_SYSTEM:
        qs = qs.filter(company=actor_profile.company)
    return qs.order_by("user__username")


def list_with_stats(actor_profile: UserProfile):
    users = list(manageable_queryset(actor_profile))
    total = len(users)
    active = sum(
        1
        for profile in users
        if profile.user.is_active and profile.status == UserProfile.STATUS_ACTIVE
    )
    security_pending = sum(1 for profile in users if not profile.is_security_complete)
    companies = (
        len({profile.company_id for profile in users})
        if actor_profile.user_type == UserProfile.USER_ADMIN
        else 0
    )
    return users, {
        "total": total,
        "active": active,
        "inactive": total - active,
        "security_pending": security_pending,
        "companies": companies,
    }


def get_manageable_user(actor_profile: UserProfile, pk) -> UserProfile:
    return get_object_or_404(manageable_queryset(actor_profile), pk=pk)


def _optional_model(app_label: str, model_name: str):
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None


def get_detail_context(profile: UserProfile) -> dict:
    uf_count = 0
    projects_count = 0

    if profile.user_type == UserProfile.USER_SYSTEM:
        uf_count = UserProfile.objects.filter(
            company=profile.company,
            user_type=UserProfile.USER_FINAL,
        ).count()

    if profile.user_type == UserProfile.USER_FINAL:
        ProjectMembership = _optional_model("projects", "ProjectMembership")
        if ProjectMembership is not None:
            projects_count = ProjectMembership.objects.filter(
                user=profile.user,
                is_active=True,
            ).count()

    return {
        "uf_count": uf_count,
        "projects_count": projects_count,
    }


def get_delete_context(profile: UserProfile) -> dict:
    detail = get_detail_context(profile)
    has_dependencies = False

    if profile.user_type == UserProfile.USER_FINAL:
        ProjectMembership = _optional_model("projects", "ProjectMembership")
        if ProjectMembership is not None:
            has_dependencies = ProjectMembership.objects.filter(user=profile.user).exists()

    if profile.user_type == UserProfile.USER_SYSTEM:
        detail["uf_count"] = UserProfile.objects.filter(
            company=profile.company,
            user_type=UserProfile.USER_FINAL,
        ).count()

    return {
        **detail,
        "has_dependencies": has_dependencies,
    }


def companies_for_picker():
    return Company.objects.filter(is_active=True).order_by("name_short")


def posted_from_request(post, actor_profile: UserProfile, profile: UserProfile | None = None) -> dict:
    scope = get_management_scope(actor_profile)
    data = {
        "username": post.get("username", "").strip(),
        "email": post.get("email", "").strip(),
        "first_name": post.get("first_name", "").strip(),
        "last_name": post.get("last_name", "").strip(),
        "password": post.get("password", ""),
        "is_active": post.get("is_active") == "1",
        "user_type": scope["target_type"],
    }
    if scope["show_company_picker"]:
        data["company_id"] = post.get("company", "").strip()
    elif scope["fixed_company"] is not None:
        data["company_id"] = str(scope["fixed_company"].pk)
    elif profile is not None:
        data["company_id"] = str(profile.company_id)
    return data


def default_posted(actor_profile: UserProfile, profile: UserProfile | None = None) -> dict:
    scope = get_management_scope(actor_profile)
    if profile is None:
        company_id = ""
        if scope["fixed_company"] is not None:
            company_id = str(scope["fixed_company"].pk)
        return {
            "username": "",
            "email": "",
            "first_name": "",
            "last_name": "",
            "password": "",
            "is_active": True,
            "user_type": scope["target_type"],
            "company_id": company_id,
        }

    return {
        "username": profile.user.username,
        "email": profile.user.email,
        "first_name": profile.user.first_name,
        "last_name": profile.user.last_name,
        "password": "",
        "is_active": profile.user.is_active and profile.status == UserProfile.STATUS_ACTIVE,
        "user_type": profile.user_type,
        "company_id": str(profile.company_id),
    }


def _resolve_company(actor_profile: UserProfile, data: dict) -> tuple[Company | None, dict[str, list[str]]]:
    scope = get_management_scope(actor_profile)
    errors: dict[str, list[str]] = {}
    company_id = data.get("company_id", "").strip()

    if not company_id:
        errors.setdefault("company", []).append("Seleccione una compañía.")
        return None, errors

    try:
        company_uuid = uuid.UUID(company_id)
    except ValueError:
        errors.setdefault("company", []).append("Compañía no válida.")
        return None, errors

    try:
        company = Company.objects.get(pk=company_uuid, is_active=True)
    except Company.DoesNotExist:
        errors.setdefault("company", []).append("Seleccione una compañía activa.")
        return None, errors

    if actor_profile.user_type == UserProfile.USER_SYSTEM and company.pk != actor_profile.company_id:
        errors.setdefault("company", []).append("No puede asignar otra compañía.")

    if scope["target_type"] == UserProfile.USER_SYSTEM and actor_profile.user_type != UserProfile.USER_ADMIN:
        errors.setdefault("company", []).append("No puede asignar compañía.")

    return company, errors


def validate_account_data(
    data: dict,
    actor_profile: UserProfile,
    profile: UserProfile | None = None,
    *,
    is_create: bool,
) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    scope = get_management_scope(actor_profile)

    if is_create:
        username = data.get("username", "").strip()
        if not username:
            errors.setdefault("username", []).append("Ingrese el nombre de usuario.")
        elif len(username) > 150:
            errors.setdefault("username", []).append("Máximo 150 caracteres.")
        elif not USERNAME_RE.match(username):
            errors.setdefault("username", []).append(
                "Use solo letras, números y los caracteres . @ + - _"
            )
        else:
            qs = User.objects.filter(username__iexact=username)
            if qs.exists():
                errors.setdefault("username", []).append(
                    "Ya existe un usuario con este nombre de usuario."
                )

        password = data.get("password", "")
        if not password:
            errors.setdefault("password", []).append("Ingrese la contraseña inicial.")
        elif len(password) < 8:
            errors.setdefault("password", []).append("Mínimo 8 caracteres.")

    email = data.get("email", "").strip()
    if not email:
        errors.setdefault("email", []).append("Ingrese el correo electrónico.")
    elif not EMAIL_RE.match(email):
        errors.setdefault("email", []).append("Ingrese un correo electrónico válido.")
    elif len(email) > 254:
        errors.setdefault("email", []).append("El correo es demasiado largo.")
    else:
        qs = User.objects.filter(email__iexact=email)
        if profile is not None:
            qs = qs.exclude(pk=profile.user_id)
        if qs.exists():
            errors.setdefault("email", []).append("Ya existe un usuario con este correo.")

    first_name = data.get("first_name", "").strip()
    if len(first_name) > 150:
        errors.setdefault("first_name", []).append("Máximo 150 caracteres.")

    last_name = data.get("last_name", "").strip()
    if len(last_name) > 150:
        errors.setdefault("last_name", []).append("Máximo 150 caracteres.")

    if data.get("user_type") != scope["target_type"]:
        errors.setdefault("user_type", []).append(
            "Solo puede crear usuarios tipo US."
            if actor_profile.user_type == UserProfile.USER_ADMIN
            else "Solo puede crear usuarios tipo UF en su compañía."
        )

    if is_create or scope["show_company_picker"]:
        _, company_errors = _resolve_company(actor_profile, data)
        errors.update(company_errors)

    return errors


def create_user(actor_profile: UserProfile, data: dict) -> OperationResult:
    scope = get_management_scope(actor_profile)
    if data.get("user_type") != scope["target_type"]:
        return OperationResult.failure(
            "forbidden_user_type",
            "Solo puede crear usuarios tipo US."
            if actor_profile.user_type == UserProfile.USER_ADMIN
            else "Solo puede crear usuarios tipo UF en su compañía.",
        )

    errors = validate_account_data(data, actor_profile, is_create=True)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    company, company_errors = _resolve_company(actor_profile, data)
    if company_errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=company_errors,
        )

    try:
        with transaction.atomic():
            user = User(
                username=data["username"],
                email=data["email"],
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                is_active=data.get("is_active", True),
            )
            user.set_password(data["password"])
            user._setup_company = company
            user._setup_user_type = scope["target_type"]
            user._setup_created_by = actor_profile.user
            user.save()

            profile = user.profile
            profile.status = (
                UserProfile.STATUS_ACTIVE
                if data.get("is_active", True)
                else UserProfile.STATUS_INACTIVE
            )
            profile.updated_by = actor_profile.user
            profile.save(update_fields=["status", "updated_by", "updated_at"])
    except IntegrityError:
        logger.exception("create_user IntegrityError username=%s", data.get("username"))
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={
                "username": ["Ya existe un usuario con este correo o nombre de usuario."],
            },
        )
    except Exception:
        logger.exception("create_user unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    success_message = (
        "Usuario administrador de compañía creado correctamente."
        if scope["target_type"] == UserProfile.USER_SYSTEM
        else "Usuario final creado correctamente."
    )
    return OperationResult.success(user_message=success_message, profile=profile)


def update_user(actor_profile: UserProfile, profile: UserProfile, data: dict) -> OperationResult:
    scope = get_management_scope(actor_profile)
    errors = validate_account_data(data, actor_profile, profile=profile, is_create=False)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    company = profile.company
    if scope["show_company_picker"]:
        company, company_errors = _resolve_company(actor_profile, data)
        if company_errors:
            return OperationResult.failure(
                "validation_form",
                "Revise los datos marcados; no se pudo guardar.",
                errors=company_errors,
            )

    try:
        with transaction.atomic():
            user = profile.user
            user.email = data["email"]
            user.first_name = data.get("first_name", "")
            user.last_name = data.get("last_name", "")
            user.is_active = data.get("is_active", False)
            user.save()

            profile.company = company
            profile.status = (
                UserProfile.STATUS_ACTIVE
                if data.get("is_active", False)
                else UserProfile.STATUS_INACTIVE
            )
            profile.updated_by = actor_profile.user
            profile.save()
    except IntegrityError:
        logger.exception("update_user IntegrityError pk=%s", profile.pk)
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"email": ["Ya existe un usuario con este correo o nombre de usuario."]},
        )
    except Exception:
        logger.exception("update_user unexpected pk=%s", profile.pk)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Usuario actualizado correctamente.",
        profile=profile,
    )


def default_password_posted() -> dict:
    return {
        "password": "",
        "password_confirm": "",
        "force_security_reset": False,
    }


def posted_password_from_request(post) -> dict:
    return {
        "password": post.get("password", ""),
        "password_confirm": post.get("password_confirm", ""),
        "force_security_reset": post.get("force_security_reset") == "1",
    }


def validate_password_data(data: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    password = data.get("password", "")
    confirm = data.get("password_confirm", "")

    if not password:
        errors.setdefault("password", []).append("Ingrese la nueva contraseña.")
    elif len(password) < 8:
        errors.setdefault("password", []).append("Mínimo 8 caracteres.")

    if not confirm:
        errors.setdefault("password_confirm", []).append("Confirme la nueva contraseña.")
    elif password != confirm:
        errors.setdefault("password_confirm", []).append("Las contraseñas no coinciden.")

    return errors


def update_password(
    actor_profile: UserProfile,
    profile: UserProfile,
    data: dict,
) -> OperationResult:
    if profile.user_id == actor_profile.user_id:
        return OperationResult.failure(
            "cannot_change_own_password",
            "Use el flujo de seguridad para cambiar su propia contraseña.",
        )

    errors = validate_password_data(data)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    force_reset = data.get("force_security_reset", False)

    try:
        with transaction.atomic():
            user = profile.user
            user.set_password(data["password"])
            user.save(update_fields=["password"])

            if force_reset:
                from apps.security.services.totp_reset import reset_security_cycle

                reset_security_cycle(profile)

            profile.updated_by = actor_profile.user
            profile.save(update_fields=["updated_by", "updated_at"])
    except Exception:
        logger.exception("update_password unexpected pk=%s", profile.pk)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    if force_reset:
        return OperationResult.success(
            user_message=(
                "Contraseña actualizada. El usuario deberá completar el ciclo de "
                "seguridad en su próximo acceso."
            ),
            profile=profile,
        )

    return OperationResult.success(
        user_message="Contraseña actualizada correctamente.",
        profile=profile,
    )


def delete_user(actor_profile: UserProfile, profile: UserProfile) -> OperationResult:
    if profile.user_id == actor_profile.user_id:
        return OperationResult.failure(
            "cannot_delete_self",
            "No puede eliminar su propia cuenta.",
        )

    delete_ctx = get_delete_context(profile)
    if delete_ctx["has_dependencies"]:
        return OperationResult.failure(
            "protected_delete",
            "No se puede eliminar el usuario: tiene proyectos o membresías activas.",
        )

    if profile.user_type == UserProfile.USER_SYSTEM:
        uf_count = UserProfile.objects.filter(
            company=profile.company,
            user_type=UserProfile.USER_FINAL,
        ).count()
        if uf_count > 0:
            return OperationResult.failure(
                "protected_delete",
                "No se puede eliminar el usuario: existen usuarios UF en su compañía.",
            )

    try:
        profile.user.delete()
    except Exception:
        logger.exception("delete_user unexpected pk=%s", profile.pk)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al eliminar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(user_message="Usuario eliminado correctamente.")
