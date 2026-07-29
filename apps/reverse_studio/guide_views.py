from django.shortcuts import render

from apps.core.decorators import security_complete_required, user_type_required


@security_complete_required
@user_type_required("UF")
def reverse_studio_guide(request):
    profile = request.user.profile
    return render(
        request,
        "reverse_studio/guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "reverse_studio_guide",
            "reverse_studio_nav_open": True,
        },
    )
