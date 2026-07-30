from django.shortcuts import render

from apps.core.decorators import security_complete_required, user_type_required


@security_complete_required
@user_type_required("UF")
def file_match_guide(request):
    profile = request.user.profile
    return render(
        request,
        "file_match/guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "file_match_guide",
            "file_match_nav_open": True,
        },
    )
