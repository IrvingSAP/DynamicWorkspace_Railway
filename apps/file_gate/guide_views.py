from django.shortcuts import render

from apps.core.decorators import security_complete_required, user_type_required


@security_complete_required
@user_type_required("UF")
def file_gate_guide(request):
    profile = request.user.profile
    return render(
        request,
        "file_gate/guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "app_nav_active": "file_gate_guide",
            "file_gate_nav_open": True,
        },
    )
