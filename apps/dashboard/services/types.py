from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class ActivityRow:
    event: str
    detail: str
    date: date | datetime
    company_short: str = ""


@dataclass
class ExpiringSubscriptionRow:
    company_short: str
    plan_name: str
    end_date: date
    status_label: str
    status_class: str


@dataclass
class ProjectRow:
    name: str
    slug: str
    role: str
    record_count: int
    updated_at: date | datetime


@dataclass
class DmsProjectRow:
    name: str
    slug: str
    role: str
    version_label: str
    updated_at: date | datetime


@dataclass
class MemberAuthRow:
    project_name: str
    username: str
    role: str
    date: date | datetime


@dataclass
class UaHomeData:
    display_name: str
    kpi_companies_total: int = 0
    kpi_companies_active: int = 0
    kpi_companies_inactive: int = 0
    kpi_users_total: int = 0
    kpi_users_active: int = 0
    kpi_users_inactive: int = 0
    kpi_projects_total: int = 0
    kpi_projects_meta: str = "En todas las compañías"
    kpi_subscriptions_active: int = 0
    kpi_subscriptions_meta: str = ""
    users_by_type: dict[str, int] = field(default_factory=dict)
    email_pending: int = 0
    tfa_pending: int = 0
    blocked_users: int = 0
    billing_available: bool = False
    top_plan_name: str = "—"
    top_plan_count: int = 0
    monthly_revenue: str = "—"
    next_expiry_label: str = "—"
    last_payment_label: str = "—"
    subs_active: int = 0
    subs_expired: int = 0
    subs_pending: int = 0
    expiring_subscriptions: list[ExpiringSubscriptionRow] = field(default_factory=list)
    activity: list[ActivityRow] = field(default_factory=list)


@dataclass
class UsHomeData:
    display_name: str
    company_short: str
    company_active: bool
    plan_name: str
    kpi_users_total: int = 0
    kpi_users_uf: int = 0
    kpi_users_us: int = 0
    kpi_users_active: int = 0
    kpi_projects_total: int = 0
    license_status: str = "Sin licencia"
    license_expiry: str = "—"
    email_pending: int = 0
    tfa_pending: int = 0
    blocked_users: int = 0
    billing_available: bool = False
    subscription_start: str = "—"
    subscription_end: str = "—"
    subscription_status_label: str = "—"
    subscription_status_class: str = ""
    last_payment_date: str = "—"
    license_row: dict[str, Any] | None = None
    activity: list[ActivityRow] = field(default_factory=list)


@dataclass
class UfHomeData:
    display_name: str
    company_short: str
    kpi_projects_total: int = 0
    kpi_projects_active: int = 0
    kpi_projects_archived: int = 0
    kpi_records_total: int = 0
    kpi_pa_count: int = 0
    kpi_dms_projects_total: int = 0
    kpi_dms_ready_count: int = 0
    kpi_dms_executions_month: int = 0
    kpi_dms_last_execution: str = "—"
    kpi_dms_ge_count: int = 0
    catalog_count: int = 0
    roles_by_type: dict[str, int] = field(default_factory=dict)
    pa_members_count: int = 0
    recent_projects: list[ProjectRow] = field(default_factory=list)
    recent_dms_projects: list[DmsProjectRow] = field(default_factory=list)
    recent_authorizations: list[MemberAuthRow] = field(default_factory=list)
    activity: list[ActivityRow] = field(default_factory=list)
    quick_project_links: list[dict[str, str]] = field(default_factory=list)
    projects_available: bool = False
