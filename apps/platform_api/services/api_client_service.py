from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.platform_api.models import (
    ALL_SCOPES,
    ENV_PROD,
    ENV_SANDBOX,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    ApiClient,
)

logger = logging.getLogger(__name__)

CODE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESCRIPTION_MAX = 2000

MSG_CREATED = "Cliente de máquina creado. Copie la key ahora; no se volverá a mostrar."
MSG_UPDATED = "Cliente actualizado. La key no cambió."
MSG_ROTATED = "Key rotada. Copie la nueva key ahora; la anterior deja de autenticar."
MSG_REVOKED = "Cliente revocado. Ya no puede autenticar llamadas."
MSG_US_ONLY = "Solo el administrador de compañía (US) puede gestionar clientes de API."
MSG_COMPANY_INACTIVE = "La compañía no está activa."
MSG_NOT_FOUND = "No se encontró el cliente de API."
MSG_VALIDATION = "Revise los datos marcados; no se pudo guardar."
MSG_DUPLICATE = "Ya existe un cliente con este código en la compañía."
MSG_UNEXPECTED = "Ocurrió un error al guardar. Si persiste, contacte al administrador."
MSG_ALREADY_REVOKED = "Este cliente ya está revocado."


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def tokens_match(raw_token: str, stored_hash: str) -> bool:
    digest = hash_token(raw_token)
    return hmac.compare_digest(digest, stored_hash)


def build_raw_token(environment: str, public_id: str, secret: str) -> str:
    prefix = "dw_live" if environment == ENV_PROD else "dw_test"
    return f"{prefix}_{public_id}.{secret}"


def mint_credentials(environment: str) -> tuple[str, str, str, str]:
    public_id = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    raw = build_raw_token(environment, public_id, secret)
    hint = secret[-4:]
    return public_id, hash_token(raw), hint, raw


def can_manage(user) -> bool:
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return False
    return (
        profile.user_type == UserProfile.USER_SYSTEM
        and profile.is_active_account
        and profile.company_id
    )


def _company_of(user):
    return user.profile.company


def list_for_user(user) -> tuple[list[ApiClient], dict]:
    company = _company_of(user)
    rows = list(
        ApiClient.objects.filter(company=company).select_related("company", "created_by")
    )
    active = sum(1 for row in rows if row.status == STATUS_ACTIVE)
    sandbox = sum(1 for row in rows if row.environment == ENV_SANDBOX and row.status == STATUS_ACTIVE)
    return rows, {
        "total": len(rows),
        "active": active,
        "revoked": len(rows) - active,
        "sandbox": sandbox,
    }


def get_for_user(user, pk) -> ApiClient | None:
    company = _company_of(user)
    return (
        ApiClient.objects.filter(pk=pk, company=company)
        .select_related("company", "created_by")
        .first()
    )


def default_posted() -> dict:
    return {
        "code": "",
        "name": "",
        "description": "",
        "environment": ENV_SANDBOX,
        "scopes": [s for s in ALL_SCOPES if s in ("jobs:run", "jobs:read")],
    }


def posted_from_request(post) -> dict:
    scopes = post.getlist("scopes") if hasattr(post, "getlist") else post.get("scopes") or []
    if isinstance(scopes, str):
        scopes = [scopes]
    return {
        "code": (post.get("code") or "").strip().lower(),
        "name": (post.get("name") or "").strip(),
        "description": (post.get("description") or "").strip(),
        "environment": (post.get("environment") or ENV_SANDBOX).strip(),
        "scopes": [s for s in scopes if s in ALL_SCOPES],
    }


def _validate(posted: dict, *, creating: bool) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    code = slugify(posted.get("code") or "")
    posted["code"] = code
    if not code:
        errors["code"] = ["Indique un código (ej. client-erp-01)."]
    elif not CODE_RE.match(code):
        errors["code"] = ["Use minúsculas, números y guiones."]
    description = (posted.get("description") or "").strip()
    posted["description"] = description
    if not description:
        errors["description"] = [
            "Indique para qué se usa esta API (sistema, proceso y responsable)."
        ]
    elif len(description) > DESCRIPTION_MAX:
        errors["description"] = [f"Máximo {DESCRIPTION_MAX} caracteres."]
    env = posted.get("environment")
    if env not in (ENV_SANDBOX, ENV_PROD):
        errors["environment"] = ["Seleccione sandbox o producción."]
    if creating and not posted.get("scopes"):
        errors["scopes"] = ["Seleccione al menos un scope."]
    unknown = [s for s in posted.get("scopes") or [] if s not in ALL_SCOPES]
    if unknown:
        errors["scopes"] = ["Scope no permitido."]
    return errors


def create_client(user, posted: dict, request=None) -> OperationResult:
    if not can_manage(user):
        return OperationResult.failure("forbidden", MSG_US_ONLY)
    company = _company_of(user)
    if not company.is_active:
        return OperationResult.failure("forbidden", MSG_COMPANY_INACTIVE)

    errors = _validate(posted, creating=True)
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    public_id, secret_hash, hint, raw = mint_credentials(posted["environment"])
    try:
        with transaction.atomic():
            client = ApiClient.objects.create(
                company=company,
                code=posted["code"],
                name=posted.get("name") or posted["code"],
                description=posted.get("description") or "",
                environment=posted["environment"],
                status=STATUS_ACTIVE,
                scopes=posted["scopes"],
                public_id=public_id,
                secret_hash=secret_hash,
                key_hint=hint,
                created_by=user,
            )
            from apps.platform_api.models import ACTION_CREATED
            from apps.platform_api.services import client_audit_service

            client_audit_service.record_event(
                client=client,
                action=ACTION_CREATED,
                actor=user,
                request=request,
                after=client_audit_service.snapshot_client(client),
            )
    except IntegrityError:
        return OperationResult.failure(
            "duplicate",
            MSG_DUPLICATE,
            errors={"code": [MSG_DUPLICATE]},
        )
    except Exception:
        logger.exception("create ApiClient failed")
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(
        MSG_CREATED,
        client=client,
        plaintext_key=raw,
    )


def update_client(user, client: ApiClient, posted: dict, request=None) -> OperationResult:
    if not can_manage(user) or client.company_id != user.profile.company_id:
        return OperationResult.failure("forbidden", MSG_US_ONLY)
    if client.status == STATUS_REVOKED:
        return OperationResult.failure("forbidden", MSG_ALREADY_REVOKED)

    errors = _validate({**posted, "environment": client.environment}, creating=False)
    if "environment" in errors:
        errors.pop("environment")
    if not posted.get("scopes"):
        errors["scopes"] = ["Seleccione al menos un scope."]
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    from apps.platform_api.models import ACTION_UPDATED
    from apps.platform_api.services import client_audit_service

    before = client_audit_service.snapshot_client(client)
    try:
        with transaction.atomic():
            client.code = posted["code"]
            client.name = posted.get("name") or posted["code"]
            client.description = posted.get("description") or ""
            client.scopes = posted["scopes"]
            client.save(update_fields=["code", "name", "description", "scopes", "updated_at"])
            after = client_audit_service.snapshot_client(client)
            if before != after:
                client_audit_service.record_event(
                    client=client,
                    action=ACTION_UPDATED,
                    actor=user,
                    request=request,
                    before=before,
                    after=after,
                )
    except IntegrityError:
        return OperationResult.failure(
            "duplicate",
            MSG_DUPLICATE,
            errors={"code": [MSG_DUPLICATE]},
        )
    except Exception:
        logger.exception("update ApiClient failed")
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(MSG_UPDATED, client=client)


def rotate_key(user, client: ApiClient, request=None) -> OperationResult:
    if not can_manage(user) or client.company_id != user.profile.company_id:
        return OperationResult.failure("forbidden", MSG_US_ONLY)
    if client.status != STATUS_ACTIVE:
        return OperationResult.failure("forbidden", MSG_ALREADY_REVOKED)
    from apps.platform_api.models import ACTION_KEY_ROTATED
    from apps.platform_api.services import client_audit_service

    before = client_audit_service.snapshot_client(client)
    public_id, secret_hash, hint, raw = mint_credentials(client.environment)
    with transaction.atomic():
        client.public_id = public_id
        client.secret_hash = secret_hash
        client.key_hint = hint
        client.save(update_fields=["public_id", "secret_hash", "key_hint", "updated_at"])
        client_audit_service.record_event(
            client=client,
            action=ACTION_KEY_ROTATED,
            actor=user,
            request=request,
            before=before,
            after=client_audit_service.snapshot_client(client),
        )
    return OperationResult.success(MSG_ROTATED, client=client, plaintext_key=raw)


def revoke_client(user, client: ApiClient, request=None) -> OperationResult:
    if not can_manage(user) or client.company_id != user.profile.company_id:
        return OperationResult.failure("forbidden", MSG_US_ONLY)
    if client.status == STATUS_REVOKED:
        return OperationResult.failure("forbidden", MSG_ALREADY_REVOKED)
    from apps.platform_api.models import ACTION_REVOKED
    from apps.platform_api.services import client_audit_service

    before = client_audit_service.snapshot_client(client)
    with transaction.atomic():
        client.status = STATUS_REVOKED
        client.revoked_at = timezone.now()
        client.save(update_fields=["status", "revoked_at", "updated_at"])
        client_audit_service.record_event(
            client=client,
            action=ACTION_REVOKED,
            actor=user,
            request=request,
            before=before,
            after=client_audit_service.snapshot_client(client),
        )
    return OperationResult.success(MSG_REVOKED, client=client)
