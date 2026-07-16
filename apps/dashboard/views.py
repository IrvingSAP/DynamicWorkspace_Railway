from django.contrib import messages

from django.shortcuts import redirect, render

from django.views.decorators.http import require_http_methods



from apps.accounts.models import UserProfile

from apps.core.decorators import security_complete_required

from apps.dashboard.services import get_ua_home_data, get_uf_home_data, get_us_home_data





@security_complete_required

def home(request):

    profile = request.user.profile



    if not profile.primer_acceso_completado:

        return redirect("dashboard:bienvenida")



    if profile.user_type == UserProfile.USER_ADMIN:

        context = {

            "dashboard": get_ua_home_data(request.user),

            "app_nav_active": "home",

        }

        return render(request, "dashboard/home_ua.html", context)



    if profile.user_type == UserProfile.USER_SYSTEM:

        context = {

            "dashboard": get_us_home_data(request.user),

            "app_nav_active": "home",

        }

        return render(request, "dashboard/home_us.html", context)



    context = {

        "dashboard": get_uf_home_data(request.user),

        "app_nav_active": "home",

        "filepipe_nav_open": False,

    }

    return render(request, "dashboard/home_uf.html", context)





@security_complete_required

@require_http_methods(["GET", "POST"])

def bienvenida(request):

    profile = request.user.profile



    if profile.primer_acceso_completado:

        return redirect("dashboard:home")



    if request.method == "POST":

        profile.primer_acceso_completado = True

        profile.save(update_fields=["primer_acceso_completado", "updated_at"])

        messages.success(request, "¡Bienvenido a DynamicWorkspace!")

        return redirect("dashboard:home")



    context = {

        "profile": profile,

        "company": profile.company,

        "display_name": request.user.get_full_name() or request.user.username,

    }

    return render(request, "dashboard/bienvenida.html", context)

