from django.shortcuts import render

from apps.core.decorators import security_complete_required, user_type_required


@security_complete_required
@user_type_required("UF")
def file_clean_guide(request):
    profile = request.user.profile
    return render(
        request,
        "file_clean/guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "file_clean_guide",
            "file_clean_nav_open": True,
        },
    )
