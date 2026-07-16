"""Tokens firmados de descarga con TTL (transform_execution.md)."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from django.conf import settings

from apps.dms.transform_execution.constants import DOWNLOAD_TTL, DOWNLOAD_KINDS


def _secret() -> bytes:
    return str(settings.SECRET_KEY).encode("utf-8")


def build_download_token(job_id: str, kind: str, *, expires_at: int | None = None) -> tuple[str, int]:
    if kind not in DOWNLOAD_KINDS:
        raise ValueError("kind inválido")
    expires = expires_at or int(time.time() + DOWNLOAD_TTL.total_seconds())
    payload = f"{job_id}:{kind}:{expires}"
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig, expires


def verify_download_token(job_id: str, kind: str, expires: str | int, signature: str) -> bool:
    if kind not in DOWNLOAD_KINDS:
        return False
    try:
        exp = int(expires)
    except (TypeError, ValueError):
        return False
    if exp < int(time.time()):
        return False
    payload = f"{job_id}:{kind}:{exp}"
    expected = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def download_querystring(job_id: str, kind: str) -> str:
    sig, expires = build_download_token(job_id, kind)
    return urlencode({"expires": expires, "sig": sig})
