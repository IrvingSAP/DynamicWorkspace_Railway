from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from apps.dashboard.services._models import get_model_optional
from apps.dashboard.services.types import (
    ActivityRow,
    DmsProjectRow,
    MemberAuthRow,
    ProjectRow,
    UfHomeData,
)
from apps.projects.models import Project

User = get_user_model()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)


def get_uf_home_data(user) -> UfHomeData:
    profile = user.profile
    company = profile.company
    display_name = user.get_full_name() or user.username

    data = UfHomeData(
        display_name=display_name,
        company_short=company.name_short,
    )

    ProjectMembership = get_model_optional("projects", "ProjectMembership")
    Record = get_model_optional("records", "Record")

    if ProjectMembership is None:
        _fill_dms_kpis(data, user)
        return data

    data.projects_available = True
    memberships = ProjectMembership.objects.filter(
        user=user,
        is_active=True,
        project__company=company,
    ).select_related("project")

    workspace_memberships = memberships.filter(
        project__project_kind=Project.KIND_WORKSPACE,
    )
    workspace_ids = list(workspace_memberships.values_list("project_id", flat=True))
    projects_qs = Project.objects.filter(
        id__in=workspace_ids,
        project_kind=Project.KIND_WORKSPACE,
    )

    data.kpi_projects_total = projects_qs.count()
    data.kpi_projects_active = projects_qs.filter(is_archived=False).count()
    data.kpi_projects_archived = projects_qs.filter(is_archived=True).count()

    role_counts = {
        row["role"]: row["count"]
        for row in workspace_memberships.values("role").annotate(count=Count("id"))
    }
    data.roles_by_type = {
        "PA": role_counts.get("PA", 0),
        "ED": role_counts.get("ED", 0),
        "CO": role_counts.get("CO", 0),
        "GE": role_counts.get("GE", 0),
    }
    data.kpi_pa_count = data.roles_by_type.get("PA", 0)

    pa_project_ids = workspace_memberships.filter(role="PA").values_list(
        "project_id", flat=True
    )
    if pa_project_ids:
        data.pa_members_count = (
            ProjectMembership.objects.filter(
                project_id__in=pa_project_ids,
                is_active=True,
            )
            .exclude(user=user)
            .count()
        )

    if Record is not None and workspace_ids:
        data.kpi_records_total = Record.objects.filter(
            project_id__in=workspace_ids,
            is_deleted=False,
        ).count()

    for membership in workspace_memberships.order_by("-project__updated_at")[:6]:
        project = membership.project
        record_count = 0
        if Record is not None:
            record_count = Record.objects.filter(
                project=project,
                is_deleted=False,
            ).count()
        data.recent_projects.append(
            ProjectRow(
                name=project.name,
                slug=project.slug,
                role=membership.role,
                record_count=record_count,
                updated_at=project.updated_at,
            )
        )

    pa_memberships = workspace_memberships.filter(role="PA")
    if pa_memberships.exists():
        auth_qs = (
            ProjectMembership.objects.filter(
                project_id__in=pa_memberships.values_list("project_id", flat=True),
                is_active=True,
            )
            .exclude(user=user)
            .select_related("user", "project")
            .order_by("-created_at")[:6]
        )
        for membership in auth_qs:
            data.recent_authorizations.append(
                MemberAuthRow(
                    project_name=membership.project.name,
                    username=membership.user.username,
                    role=membership.role,
                    date=membership.created_at,
                )
            )

    for project in projects_qs.order_by("-updated_at")[:3]:
        data.quick_project_links.append(
            {"name": project.name, "slug": project.slug},
        )

    data.activity = _uf_activity(user, workspace_ids, Record, ProjectMembership)
    _fill_dms_kpis(data, user)
    return data


def _fill_dms_kpis(data: UfHomeData, user) -> None:
    try:
        from apps.dms.catalogs.catalog_registry import hub_entries
        from apps.dms.file_intake.models import DmsExecutionJob
        from apps.dms.mapping.services import mapping_project_service
    except Exception:
        data.catalog_count = 0
        return

    try:
        data.catalog_count = sum(entry["count"] for entry in hub_entries())
    except Exception:
        data.catalog_count = 0

    try:
        rows, _stats = mapping_project_service.list_with_stats(user)
        data.kpi_dms_projects_total = len(rows)
        data.kpi_dms_ready_count = sum(
            1
            for row in rows
            if getattr(row["project"], "dms_config", None)
            and row["project"].dms_config.current_version_id
        )
        data.kpi_dms_ge_count = sum(1 for row in rows if row["role"] == "GE")

        dms_ids = [row["project"].id for row in rows]
        month_start = timezone.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        exec_base = DmsExecutionJob.objects.filter(
            project_id__in=dms_ids,
            job_type=DmsExecutionJob.JOB_FULL,
        ).exclude(status=DmsExecutionJob.STATUS_UPLOADED)

        data.kpi_dms_executions_month = exec_base.filter(
            created_at__gte=month_start
        ).count()

        last_job = exec_base.order_by("-created_at").first()
        if last_job is not None:
            when = last_job.finished_at or last_job.created_at
            data.kpi_dms_last_execution = _format_date(when)

        for row in rows[:6]:
            project = row["project"]
            data.recent_dms_projects.append(
                DmsProjectRow(
                    name=project.name,
                    slug=project.slug,
                    role=row["role"] or "CO",
                    version_label=row["version_label"],
                    updated_at=project.updated_at,
                )
            )
    except Exception:
        pass


def _uf_activity(user, project_ids, Record, ProjectMembership) -> list[ActivityRow]:
    rows: list[ActivityRow] = []

    if Record is not None and project_ids:
        for record in (
            Record.objects.filter(project_id__in=project_ids)
            .select_related("project")
            .order_by("-updated_at")[:6]
        ):
            rows.append(
                ActivityRow(
                    event="Registro actualizado",
                    detail=record.project.name,
                    date=record.updated_at,
                    company_short=record.project.slug,
                )
            )

    if ProjectMembership is not None and project_ids:
        for membership in (
            ProjectMembership.objects.filter(project_id__in=project_ids)
            .select_related("project", "user")
            .order_by("-created_at")[:6]
        ):
            if membership.user_id == user.id:
                continue
            rows.append(
                ActivityRow(
                    event="Miembro autorizado",
                    detail=membership.project.name,
                    date=membership.created_at,
                    company_short=membership.project.slug,
                )
            )

    if project_ids:
        for project in Project.objects.filter(
            id__in=project_ids,
            owner=user,
            project_kind=Project.KIND_WORKSPACE,
        ).order_by("-created_at")[:4]:
            rows.append(
                ActivityRow(
                    event="Proyecto creado",
                    detail=project.name,
                    date=project.created_at,
                    company_short=project.slug,
                )
            )

    rows.sort(key=lambda row: row.date, reverse=True)
    return rows[:8]
