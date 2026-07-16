from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.company.models import Company
from apps.dashboard.services._models import get_model_optional
from apps.dashboard.services.types import ActivityRow, ExpiringSubscriptionRow, UaHomeData

User = get_user_model()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "date"):
        value = value.date() if callable(getattr(value, "date", None)) else value
    return value.strftime("%d/%m/%Y")


def _subscription_status_style(status: str) -> tuple[str, str]:
    mapping = {
        "active": ("Activa", "status-active"),
        "expired": ("Vencida", "status-inactive"),
        "pending": ("Pendiente", "status-pending"),
        "cancelled": ("Cancelada", "status-inactive"),
    }
    return mapping.get(status, (status, ""))


def _collect_activity(limit: int = 8) -> list[ActivityRow]:
    rows: list[ActivityRow] = []

    for company in Company.objects.order_by("-created_at")[:limit]:
        rows.append(
            ActivityRow(
                event="Nueva compañía",
                detail=company.name_short,
                date=company.created_at,
                company_short=company.name_short,
            )
        )

    for profile in UserProfile.objects.select_related("user", "company").order_by(
        "-created_at"
    )[:limit]:
        rows.append(
            ActivityRow(
                event=f"Usuario {profile.user_type} creado",
                detail=profile.user.username,
                date=profile.created_at,
                company_short=profile.company.name_short,
            )
        )

    Payment = get_model_optional("billing", "Payment")
    if Payment is not None:
        for payment in (
            Payment.objects.select_related("subscription__company", "subscription__plan")
            .order_by("-paid_at")[:limit]
        ):
            rows.append(
                ActivityRow(
                    event="Pago registrado",
                    detail=payment.subscription.company.name_short,
                    date=payment.paid_at,
                    company_short=payment.subscription.company.name_short,
                )
            )

    Project = get_model_optional("projects", "Project")
    if Project is not None:
        for project in Project.objects.select_related("company").order_by("-created_at")[
            :limit
        ]:
            rows.append(
                ActivityRow(
                    event="Proyecto creado",
                    detail=project.name,
                    date=project.created_at,
                    company_short=project.company.name_short,
                )
            )

    rows.sort(key=lambda row: row.date, reverse=True)
    return rows[:limit]


def get_ua_home_data(user) -> UaHomeData:
    display_name = user.get_full_name() or user.username
    companies = Company.objects.all()
    profiles = UserProfile.objects.select_related("user")

    company_total = companies.count()
    company_active = companies.filter(is_active=True).count()
    company_inactive = company_total - company_active

    users_total = profiles.count()
    now = timezone.now()
    users_active = profiles.filter(
        status=UserProfile.STATUS_ACTIVE,
        user__is_active=True,
    ).filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now)).count()
    users_inactive = users_total - users_active

    users_by_type = {
        row["user_type"]: row["count"]
        for row in profiles.values("user_type").annotate(count=Count("id"))
    }

    email_pending = profiles.filter(email_confirmed=False).count()
    tfa_pending = profiles.filter(email_confirmed=True, tfa_verified=False).count()
    blocked_users = profiles.filter(
        Q(status=UserProfile.STATUS_INACTIVE)
        | Q(locked_until__gt=now)
        | Q(user__is_active=False)
    ).count()

    data = UaHomeData(
        display_name=display_name,
        kpi_companies_total=company_total,
        kpi_companies_active=company_active,
        kpi_companies_inactive=company_inactive,
        kpi_users_total=users_total,
        kpi_users_active=users_active,
        kpi_users_inactive=users_inactive,
        users_by_type=users_by_type,
        email_pending=email_pending,
        tfa_pending=tfa_pending,
        blocked_users=blocked_users,
        activity=_collect_activity(),
    )

    Project = get_model_optional("projects", "Project")
    if Project is not None:
        data.kpi_projects_total = Project.objects.count()

    Subscription = get_model_optional("billing", "Subscription")
    if Subscription is None:
        data.kpi_subscriptions_meta = "Billing pendiente de implementar"
        return data

    data.billing_available = True
    subs = Subscription.objects.select_related("company", "plan")
    data.kpi_subscriptions_active = subs.filter(status="active").count()
    data.kpi_subscriptions_meta = (
        f"De {company_total} compañía{'s' if company_total != 1 else ''} con licencia"
    )

    data.subs_active = subs.filter(status="active").count()
    data.subs_expired = subs.filter(status="expired").count()
    data.subs_pending = subs.filter(status="pending").count()

    top_plan = (
        subs.values("plan__name", "plan__code")
        .annotate(count=Count("id"))
        .order_by("-count")
        .first()
    )
    if top_plan:
        data.top_plan_name = top_plan["plan__name"] or top_plan["plan__code"]
        data.top_plan_count = top_plan["count"]

    Payment = get_model_optional("billing", "Payment")
    if Payment is not None:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        from django.db.models import Sum

        revenue = Payment.objects.filter(paid_at__gte=month_start).aggregate(
            total=Sum("amount")
        )["total"]
        if revenue is not None:
            data.monthly_revenue = f"$ {revenue:,.0f}".replace(",", ".")

        last_payment = Payment.objects.select_related("subscription__company").order_by(
            "-paid_at"
        ).first()
        if last_payment:
            data.last_payment_label = (
                f"$ {last_payment.amount:,.0f} · {_format_date(last_payment.paid_at)}"
            ).replace(",", ".")

    horizon = now.date() + timedelta(days=30)
    expiring = subs.filter(
        status="active",
        end_date__lte=horizon,
        end_date__gte=now.date(),
    ).order_by("end_date")[:10]
    for sub in expiring:
        label, css = _subscription_status_style(sub.status)
        data.expiring_subscriptions.append(
            ExpiringSubscriptionRow(
                company_short=sub.company.name_short,
                plan_name=sub.plan.name if sub.plan_id else "—",
                end_date=sub.end_date,
                status_label=label,
                status_class=css,
            )
        )

    next_sub = subs.filter(status="active").order_by("end_date").first()
    if next_sub:
        data.next_expiry_label = (
            f"{next_sub.company.name_short} · {_format_date(next_sub.end_date)}"
        )

    return data
