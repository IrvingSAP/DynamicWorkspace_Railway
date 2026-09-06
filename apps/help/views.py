from django.shortcuts import redirect, render

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


US_GENERAL_GUIDES = {
    "company": ("Compañía", "us_help_company", "help/us_guide_stub.html"),
    "accounts": ("Cuentas", "us_help_accounts", "help/us_guide_stub.html"),
    "users": ("Usuarios", "us_help_users", "help/us_guide_stub.html"),
    "api-clients": ("Clientes API", "us_help_api_clients", "help/us_api_clients_guide.html"),
    "api-contract": ("Contrato API", "us_help_api_contract", "help/us_api_contract_guide.html"),
    "api-paths": ("Paths API", "us_help_api_paths", "help/us_api_paths_guide.html"),
    "api-integration": ("Integración API", "us_help_api_integration", "help/us_api_integration_guide.html"),
    "api-security": ("Seguridad API", "us_help_api_security", "help/us_api_security_guide.html"),
    "api-audit": ("Auditoría API", "us_help_api_audit", "help/us_api_audit_guide.html"),
    "manual-jobs": ("Jobs sueltos", "us_help_manual_jobs", "help/us_manual_jobs_meta.html"),
    "manual-pipelines": ("Pipelines", "us_help_manual_pipelines", "help/us_guide_stub.html"),
    "file-scheduler": ("File Scheduler", "us_help_file_scheduler", "help/us_guide_stub.html"),
    "file-watch": ("File Watch", "us_help_file_watch", "help/us_guide_stub.html"),
}


def _us_help_ctx(request, nav, **extra):
    profile = request.user.profile
    return {
        "profile": profile,
        "company": profile.company,
        "app_nav_active": nav,
        **extra,
    }


@security_complete_required
@user_type_required(UserProfile.USER_SYSTEM)
def us_manual_jobs(request):
    return render(
        request,
        "help/us_manual_jobs.html",
        _us_help_ctx(request, "us_manual_jobs"),
    )


@security_complete_required
@user_type_required(UserProfile.USER_SYSTEM)
def us_manual_pipelines(request):
    return render(
        request,
        "help/us_manual_pipelines.html",
        _us_help_ctx(request, "us_manual_pipelines"),
    )


@security_complete_required
@user_type_required(UserProfile.USER_SYSTEM)
def us_general_guide(request, topic):
    spec = US_GENERAL_GUIDES.get(topic)
    if spec is None:
        return redirect("dashboard:home")
    title, nav, template = spec
    profile = request.user.profile
    return render(
        request,
        template,
        {
            "profile": profile,
            "company": profile.company,
            "guide_title": title,
            "app_nav_active": nav,
        },
    )


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
