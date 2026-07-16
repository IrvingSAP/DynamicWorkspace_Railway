from django.contrib.auth import get_user_model

from apps.security.constants import SECURITY_PENDING_USER_KEY

User = get_user_model()


def set_pending_user(request, user_id: int) -> None:
    request.session[SECURITY_PENDING_USER_KEY] = user_id
    request.session.modified = True


def clear_pending_user(request) -> None:
    request.session.pop(SECURITY_PENDING_USER_KEY, None)
    request.session.modified = True


def get_pending_user_id(request) -> int | None:
    value = request.session.get(SECURITY_PENDING_USER_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_pending_user(request):
    user_id = get_pending_user_id(request)
    if user_id is None:
        return None
    try:
        return User.objects.select_related("profile", "profile__company").get(pk=user_id)
    except User.DoesNotExist:
        clear_pending_user(request)
        return None
