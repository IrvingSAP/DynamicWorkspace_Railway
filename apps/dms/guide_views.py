from django.shortcuts import render

from apps.core.decorators import security_complete_required, user_type_required


@security_complete_required
@user_type_required("UF")
def datamapping_guide(request):
    profile = request.user.profile
    return render(
        request,
        "dms/datamapping_guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "filepipe_guide",
            "filepipe_nav_open": True,
        },
    )
