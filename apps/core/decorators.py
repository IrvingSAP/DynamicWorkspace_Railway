from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from apps.security.services.profile_routing import resolve_security_step_name
from apps.security.services.security_session import get_pending_user


def pending_security_user_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = get_pending_user(request)
        if user is None:
            return redirect("security:login")
        request.security_user = user
        request.security_profile = user.profile
        return view_func(request, *args, **kwargs)

    return wrapper


def security_complete_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            profile = request.user.profile
        except Exception:
            return redirect("security:login")
        if not profile.is_security_complete:
            return redirect(resolve_security_step_name(profile))
        return view_func(request, *args, **kwargs)

    return wrapper


def user_type_required(*allowed_types: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.contrib import messages

            try:
                profile = request.user.profile
            except Exception:
                return redirect("security:login")
            if profile.user_type not in allowed_types:
                messages.error(
                    request,
                    "No tiene permiso para realizar esta operación.",
                )
                return redirect("dashboard:home")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
