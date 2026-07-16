from django.shortcuts import render

from apps.accounts.models import UserProfile
from apps.core.decorators import security_complete_required, user_type_required
from apps.projects.models import ProjectMembership


def _example_project(user):
    membership = (
        ProjectMembership.objects.filter(
            user=user,
            is_active=True,
            project__is_archived=False,
        )
        .select_related("project", "project__company")
        .order_by("-project__updated_at")
        .first()
    )
    return membership.project if membership else None


@security_complete_required
@user_type_required(UserProfile.USER_FINAL)
def uf_guide(request):
    profile = request.user.profile
    example_project = _example_project(request.user)
    return render(
        request,
        "help/uf_guide.html",
        {
            "profile": profile,
            "company": profile.company,
            "example_project": example_project,
            "app_nav_active": "help",
        },
    )
