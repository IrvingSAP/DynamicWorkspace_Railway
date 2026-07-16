"""Persistencia temporal de formularios en sesión (PRG tras validación fallida)."""

from datetime import date, datetime
from decimal import Decimal

FORM_SESSION_PREFIX = "dw_form:"

_SKIP_KEYS = frozenset({"logo", "password", "password_confirm"})


def _serialize_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return None


def _serializable_posted(posted: dict) -> dict:
    result = {}
    for key, value in posted.items():
        if key in _SKIP_KEYS or key.startswith("_"):
            continue
        if hasattr(value, "read"):
            continue
        serialized = _serialize_value(value)
        if serialized is not None:
            result[key] = serialized
    return result


def stash_form_state(
    request,
    namespace: str,
    posted: dict,
    errors: dict | None = None,
) -> None:
    request.session[f"{FORM_SESSION_PREFIX}{namespace}"] = {
        "posted": _serializable_posted(posted),
        "errors": errors or {},
    }
    request.session.modified = True


def take_form_state(request, namespace: str) -> dict | None:
    return request.session.pop(f"{FORM_SESSION_PREFIX}{namespace}", None)


def clear_form_state(request, namespace: str) -> None:
    request.session.pop(f"{FORM_SESSION_PREFIX}{namespace}", None)
    request.session.modified = True
