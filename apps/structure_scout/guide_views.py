from django.shortcuts import render

from apps.core.decorators import security_complete_required, user_type_required


@security_complete_required
@user_type_required("UF")
def structure_scout_guide(request):
    profile = request.user.profile
    return render(
        request,
        "structure_scout/guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "structure_scout_guide",
            "structure_scout_nav_open": True,
        },
    )
