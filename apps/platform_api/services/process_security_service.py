from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
from urllib.parse import urlparse

from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.platform_api.models import (
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_ARTIFACT_TTL_HOURS,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_RATE_PER_MINUTE,
    ApiClient,
    ApiProcessPolicy,
)
from apps.platform_api.services.api_client_service import can_manage
from apps.platform_api.services.bearer_auth import AuthFailure

logger = logging.getLogger(__name__)

MSG_SAVED = "Política de proceso API actualizada."
MSG_US_ONLY = "Solo el administrador de compañía (US) puede gestionar la política de proceso API."
MSG_VALIDATION = "Revise los datos marcados; no se pudo guardar."
MSG_RATE = "Demasiadas solicitudes. Espere un minuto e intente de nuevo."
MSG_TOO_LARGE = "El archivo supera el tamaño máximo permitido para esta compañía."
MSG_BAD_TYPE = "Tipo de archivo no permitido. Use los mismos tipos que en la carga de la app."
MSG_CALLBACK = "La URL de callback no está permitida."
MSG_UNPUBLISHED = "Solo se puede ejecutar una versión publicada."
MSG_NOT_FOUND = "No se encontró el recurso."
MSG_ARTIFACT = "El enlace del artifact no es válido o ya expiró."

PII_KEYS = frozenset(
    {
        "authorization",
        "password",
        "secret",
        "token",
        "file",
        "body",
        "payload",
        "cells",
        "content",
        "plaintext_key",
    }
)
HOST_RE = re.compile(r"^[a-z0-9.-]+$")
ARTIFACT_SALT = "platform-api-artifact-v1"


def redact_for_log(data: dict | None) -> dict:
    safe: dict = {}
    for key, value in (data or {}).items():
        if str(key).lower() in PII_KEYS:
            safe[key] = "[redacted]"
        else:
            safe[key] = value
    return safe


def get_policy(company) -> ApiProcessPolicy:
    policy, _created = ApiProcessPolicy.objects.get_or_create(
        company=company,
        defaults={
            "max_upload_bytes": DEFAULT_MAX_UPLOAD_BYTES,
            "rate_per_minute": DEFAULT_RATE_PER_MINUTE,
            "artifact_ttl_hours": DEFAULT_ARTIFACT_TTL_HOURS,
            "allowed_extensions": list(DEFAULT_ALLOWED_EXTENSIONS),
            "webhook_host_allowlist": [],
            "require_published": True,
            "dry_run_counts_in_dashboard": False,
        },
    )
    if not policy.allowed_extensions:
        policy.allowed_extensions = list(DEFAULT_ALLOWED_EXTENSIONS)
        policy.save(update_fields=["allowed_extensions"])
    return policy


def get_policy_for_user(user) -> ApiProcessPolicy | None:
    if not can_manage(user):
        return None
    return get_policy(user.profile.company)


def posted_from_request(post) -> dict:
    hosts_raw = (post.get("webhook_host_allowlist") or "").replace(",", "\n")
    hosts = [line.strip().lower() for line in hosts_raw.splitlines() if line.strip()]
    exts_raw = (post.get("allowed_extensions") or "").replace(",", " ")
    exts = []
    for token in exts_raw.split():
        item = token.strip().lower()
        if not item:
            continue
        if not item.startswith("."):
            item = f".{item}"
        exts.append(item)
    return {
        "max_upload_mb": (post.get("max_upload_mb") or "").strip(),
        "rate_per_minute": (post.get("rate_per_minute") or "").strip(),
        "artifact_ttl_hours": (post.get("artifact_ttl_hours") or "").strip(),
        "allowed_extensions": exts,
        "webhook_host_allowlist": hosts,
    }


def default_posted(policy: ApiProcessPolicy) -> dict:
    return {
        "max_upload_mb": str(max(1, policy.max_upload_bytes // (1024 * 1024))),
        "rate_per_minute": str(policy.rate_per_minute),
        "artifact_ttl_hours": str(policy.artifact_ttl_hours),
        "allowed_extensions": " ".join(policy.extension_list()),
        "webhook_host_allowlist": "\n".join(policy.webhook_hosts()),
        "require_published": True,
        "dry_run_counts_in_dashboard": False,
    }


def _positive_int(raw: str, *, minimum: int, maximum: int) -> int | None:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value < minimum or value > maximum:
        return None
    return value


def update_policy(user, posted: dict) -> OperationResult:
    if not can_manage(user):
        return OperationResult.failure("forbidden", MSG_US_ONLY)
    errors: dict[str, list[str]] = {}
    mb = _positive_int(posted.get("max_upload_mb") or "", minimum=1, maximum=500)
    if mb is None:
        errors["max_upload_mb"] = ["Indique un tamaño entre 1 y 500 MB (alineado al intake)."]
    rate = _positive_int(posted.get("rate_per_minute") or "", minimum=1, maximum=600)
    if rate is None:
        errors["rate_per_minute"] = ["Indique entre 1 y 600 solicitudes por minuto."]
    ttl = _positive_int(posted.get("artifact_ttl_hours") or "", minimum=1, maximum=168)
    if ttl is None:
        errors["artifact_ttl_hours"] = ["Indique un TTL entre 1 y 168 horas."]
    hosts = posted.get("webhook_host_allowlist") or []
    bad_hosts = [h for h in hosts if not HOST_RE.match(h) or h.startswith(".")]
    if bad_hosts:
        errors["webhook_host_allowlist"] = [
            "Hosts inválidos. Use nombres (ej. hooks.banco.example), uno por línea."
        ]
    exts = posted.get("allowed_extensions") or list(DEFAULT_ALLOWED_EXTENSIONS)
    if not exts:
        errors["allowed_extensions"] = ["Indique al menos una extensión (ej. .txt .csv)."]
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    policy = get_policy(user.profile.company)
    policy.max_upload_bytes = mb * 1024 * 1024
    policy.rate_per_minute = rate
    policy.artifact_ttl_hours = ttl
    policy.allowed_extensions = exts
    policy.webhook_host_allowlist = hosts
    policy.require_published = True
    policy.dry_run_counts_in_dashboard = False
    policy.updated_by = user
    policy.save()
    logger.info(
        "api process policy updated",
        extra=redact_for_log(
            {"company_id": str(policy.company_id), "actor": getattr(user, "username", "")}
        ),
    )
    return OperationResult.success(MSG_SAVED, policy=policy)


def enforce_rate_limit(client: ApiClient) -> None:
    policy = get_policy(client.company)
    bucket = timezone.now().strftime("%Y%m%d%H%M")
    cache_key = f"pa-rate:{client.pk}:{bucket}"
    count = cache.get(cache_key, 0) + 1
    cache.set(cache_key, count, timeout=70)
    if count > policy.rate_per_minute:
        logger.info(
            "api rate limited",
            extra=redact_for_log({"client_id": str(client.pk), "count": count}),
        )
        raise AuthFailure(429, "rate_limited", MSG_RATE)


def validate_upload(*, filename: str, size_bytes: int, company) -> OperationResult:
    policy = get_policy(company)
    name = (filename or "").lower()
    ext = ""
    if "." in name:
        ext = "." + name.rsplit(".", 1)[-1]
    if ext not in policy.extension_list():
        return OperationResult.failure(
            "validation_form",
            MSG_BAD_TYPE,
            errors={"file": [MSG_BAD_TYPE]},
        )
    if size_bytes > policy.max_upload_bytes:
        return OperationResult.failure(
            "validation_form",
            MSG_TOO_LARGE,
            errors={"file": [MSG_TOO_LARGE]},
        )
    return OperationResult.success("")


def _is_blocked_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        lowered = host.lower().rstrip(".")
        return lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".localhost")
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_callback_url(url: str, company) -> OperationResult:
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        return OperationResult.failure(
            "validation_form", MSG_CALLBACK, errors={"callback_url": [MSG_CALLBACK]}
        )
    host = parsed.hostname.lower()
    if parsed.username or parsed.password:
        return OperationResult.failure(
            "validation_form", MSG_CALLBACK, errors={"callback_url": [MSG_CALLBACK]}
        )
    if _is_blocked_host(host):
        return OperationResult.failure(
            "validation_form", MSG_CALLBACK, errors={"callback_url": [MSG_CALLBACK]}
        )
    allow = get_policy(company).webhook_hosts()
    if not allow or host not in allow:
        return OperationResult.failure(
            "validation_form", MSG_CALLBACK, errors={"callback_url": [MSG_CALLBACK]}
        )
    return OperationResult.success("")


def ensure_published(*, is_published: bool) -> None:
    if not is_published:
        raise AuthFailure(409, "unpublished", MSG_UNPUBLISHED)


def opaque_not_found() -> AuthFailure:
    return AuthFailure(404, "not_found", MSG_NOT_FOUND)


def artifact_ttl_seconds(company) -> int:
    return get_policy(company).artifact_ttl_hours * 3600


def sign_artifact_token(*, company_id, job_id: str, name: str) -> str:
    signer = TimestampSigner(salt=ARTIFACT_SALT)
    return signer.sign(f"{company_id}:{job_id}:{name}")


def read_artifact_token(token: str, *, max_age: int) -> tuple[str, str, str]:
    signer = TimestampSigner(salt=ARTIFACT_SALT)
    try:
        raw = signer.unsign(token, max_age=max_age)
    except (BadSignature, SignatureExpired) as exc:
        raise AuthFailure(404, "not_found", MSG_ARTIFACT) from exc
    parts = raw.split(":")
    if len(parts) < 3:
        raise opaque_not_found()
    return str(parts[0]), str(parts[1]), ":".join(parts[2:])


def verify_artifact_token(token: str, *, company_id, max_age: int) -> tuple[str, str]:
    token_company, job_id, name = read_artifact_token(token, max_age=max_age)
    if token_company != str(company_id):
        raise opaque_not_found()
    return job_id, name


def idempotency_fingerprint(idempotency_key: str, body_hash: str) -> str:
    return hashlib.sha256(f"{idempotency_key}:{body_hash}".encode("utf-8")).hexdigest()


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dry_run_in_dashboard(company) -> bool:
    return bool(get_policy(company).dry_run_counts_in_dashboard)
