from __future__ import annotations

import logging
import re

from django.utils import timezone

from apps.platform_api.models import ApiClient, STATUS_ACTIVE
from apps.platform_api.services.api_client_service import tokens_match

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(
    r"^dw_(live|test)_([0-9a-f]{16})\.([A-Za-z0-9_-]+)$"
)

MSG_NO_TOKEN = "Credencial ausente o inválida."
MSG_FORBIDDEN = "No tiene permiso para esta operación."
MSG_COMPANY = "La compañía no puede usar la API en este momento."


class AuthFailure(Exception):
    def __init__(self, status: int, error_code: str, user_message: str):
        self.status = status
        self.error_code = error_code
        self.user_message = user_message
        super().__init__(user_message)


def parse_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def authenticate_token(raw_token: str) -> ApiClient:
    match = TOKEN_RE.match(raw_token)
    if not match:
        raise AuthFailure(401, "invalid_token", MSG_NO_TOKEN)
    _env, public_id, _secret = match.groups()
    client = (
        ApiClient.objects.select_related("company")
        .filter(public_id=public_id)
        .first()
    )
    if client is None or not tokens_match(raw_token, client.secret_hash):
        raise AuthFailure(401, "invalid_token", MSG_NO_TOKEN)
    if client.status != STATUS_ACTIVE:
        raise AuthFailure(401, "invalid_token", MSG_NO_TOKEN)
    if not client.company.is_active:
        raise AuthFailure(403, "company_inactive", MSG_COMPANY)
    ApiClient.objects.filter(pk=client.pk).update(last_used_at=timezone.now())
    return client


def require_scopes(client: ApiClient, *scopes: str) -> None:
    missing = [s for s in scopes if not client.has_scope(s)]
    if missing:
        raise AuthFailure(403, "insufficient_scope", MSG_FORBIDDEN)
