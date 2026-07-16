from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.dashboard.services._models import get_model_optional
from apps.dashboard.services.types import ActivityRow, UsHomeData

User = get_user_model()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "date"):
        dt = value.date() if callable(getattr(value, "date", None)) else value
    else:
        dt = value
    return dt.strftime("%d/%m/%Y")


def _subscription_status_style(status: str) -> tuple[str, str]:
    mapping = {
        "active": ("Activa", "status-active"),
        "expired": ("Vencida", "status-inactive"),
        "pending": ("Pendiente", "status-pending"),
        "cancelled": ("Cancelada", "status-inactive"),
    }
    return mapping.get(status, (status, ""))


def _company_activity(company, limit: int = 8) -> list[ActivityRow]:
    rows: list[ActivityRow] = []

    for profile in (
        UserProfile.objects.filter(company=company)
        .select_related("user")
        .order_by("-created_at")[:limit]
    ):
        rows.append(
            ActivityRow(
                event=f"Usuario {profile.user_type} creado",
                detail=profile.user.username,
                date=profile.created_at,
            )
        )

    Project = get_model_optional("projects", "Project")
    if Project is not None:
        for project in Project.objects.filter(company=company).order_by("-created_at")[
            :limit
        ]:
            rows.append(
                ActivityRow(
                    event="Proyecto creado",
                    detail=project.name,
                    date=project.created_at,
                )
            )

    ProjectMembership = get_model_optional("projects", "ProjectMembership")
    if ProjectMembership is not None:
        for membership in (
            ProjectMembership.objects.filter(project__company=company)
            .select_related("user", "project")
            .order_by("-created_at")[:limit]
        ):
            rows.append(
                ActivityRow(
                    event="Miembro autorizado",
                    detail=membership.project.name,
                    date=membership.created_at,
                )
            )

    rows.sort(key=lambda row: row.date, reverse=True)
    return rows[:limit]


def get_us_home_data(user) -> UsHomeData:
    profile = user.profile
    company = profile.company
    display_name = user.get_full_name() or user.username
    profiles = UserProfile.objects.filter(company=company).select_related("user")
    now = timezone.now()

    uf_count = profiles.filter(user_type=UserProfile.USER_FINAL).count()
    us_count = profiles.filter(user_type=UserProfile.USER_SYSTEM).count()
    users_total = profiles.count()
    users_active = profiles.filter(
        status=UserProfile.STATUS_ACTIVE,
        user__is_active=True,
    ).filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now)).count()

    data = UsHomeData(
        display_name=display_name,
        company_short=company.name_short,
        company_active=company.is_active,
        plan_name="—",
        kpi_users_total=users_total,
        kpi_users_uf=uf_count,
        kpi_users_us=us_count,
        kpi_users_active=users_active,
        email_pending=profiles.filter(email_confirmed=False).count(),
        tfa_pending=profiles.filter(email_confirmed=True, tfa_verified=False).count(),
        blocked_users=profiles.filter(
            Q(status=UserProfile.STATUS_INACTIVE)
            | Q(locked_until__gt=now)
            | Q(user__is_active=False)
        ).count(),
        activity=_company_activity(company),
    )

    Project = get_model_optional("projects", "Project")
    if Project is not None:
        data.kpi_projects_total = Project.objects.filter(company=company).count()

    Subscription = get_model_optional("billing", "Subscription")
    if Subscription is None:
        data.license_status = "Sin licencia"
        return data

    try:
        subscription = Subscription.objects.select_related("plan").get(company=company)
    except Subscription.DoesNotExist:
        data.license_status = "Sin licencia"
        return data

    data.billing_available = True
    status_label, status_class = _subscription_status_style(subscription.status)
    data.license_status = status_label
    data.license_expiry = _format_date(subscription.end_date)
    data.plan_name = subscription.plan.name if subscription.plan_id else "—"
    data.subscription_start = _format_date(subscription.start_date)
    data.subscription_end = _format_date(subscription.end_date)
    data.subscription_status_label = status_label
    data.subscription_status_class = status_class
    data.license_row = {
        "plan": data.plan_name,
        "start": data.subscription_start,
        "end": data.subscription_end,
        "status_label": status_label,
        "status_class": status_class,
    }

    Payment = get_model_optional("billing", "Payment")
    if Payment is not None:
        last_payment = (
            Payment.objects.filter(subscription=subscription).order_by("-paid_at").first()
        )
        if last_payment:
            data.last_payment_date = _format_date(last_payment.paid_at)

    return data
