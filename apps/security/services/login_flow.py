import logging

from django.contrib.auth import authenticate, get_user_model

from apps.core.services.operation_result import OperationResult
from apps.security.services.profile_routing import resolve_security_step_name

User = get_user_model()
logger = logging.getLogger(__name__)


def authenticate_credentials(username: str, password: str) -> OperationResult:
    username = (username or "").strip()
    password = password or ""

    if not username or not password:
        return OperationResult.failure(
            "validation_form",
            "Ingrese usuario y contraseña.",
            errors={
                "username": ["Ingrese su usuario."] if not username else [],
                "password": ["Ingrese su contraseña."] if not password else [],
            },
        )

    try:
        user = User.objects.select_related("profile", "profile__company").get(
            username=username
        )
    except User.DoesNotExist:
        return OperationResult.failure(
            "not_found",
            "Usuario no encontrado.",
        )

    auth_user = authenticate(username=username, password=password)
    if auth_user is None:
        return OperationResult.failure(
            "unauthorized",
            "Contraseña incorrecta. Si olvidaste tu contraseña, contacta al administrador.",
        )

    try:
        profile = user.profile
    except Exception:
        logger.exception("User %s has no profile", username)
        return OperationResult.failure(
            "unexpected",
            "Tu perfil no está configurado. Contacta al administrador.",
        )

    if not profile.is_active_account:
        return OperationResult.failure(
            "business_blocked",
            "Tu cuenta está temporalmente bloqueada. Intenta más tarde.",
        )

    if not user.email:
        return OperationResult.failure(
            "business_blocked",
            "Tu cuenta no tiene correo configurado. Contacta al administrador.",
        )

    next_step = resolve_security_step_name(profile)
    return OperationResult.success(
        payload={
            "user": user,
            "profile": profile,
            "next_step": next_step,
        },
    )
