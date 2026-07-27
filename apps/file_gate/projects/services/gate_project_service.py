import logging

from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.dms.mapping.models import DmsProjectConfig
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

VISIBILITY_LABELS = {
    DmsProjectConfig.VISIBILITY_COMPANY: "Público",
    DmsProjectConfig.VISIBILITY_MEMBERS_ONLY: "Privado",
}

ROLE_LABELS = {
    **project_service.ROLE_LABELS,
    "company_viewer": "CO — Consulta (compañía)",
}


def user_can_view(user, project: Project) -> bool:
    if project.project_kind != Project.KIND_FILE_GATE:
        return False
    if project.company_id != user.profile.company_id:
        return False
    if project_service.get_membership(user, project) is not None:
        return True
    config = getattr(project, "dms_config", None)
    if config is None:
        return False
    return config.visibility == DmsProjectConfig.VISIBILITY_COMPANY


def get_project_for_user(user, slug: str) -> Project | None:
    profile = user.profile
    try:
        project = Project.objects.select_related(
            "company",
            "owner",
            "dms_config",
        ).get(
            company=profile.company,
            slug=slug,
            project_kind=Project.KIND_FILE_GATE,
        )
    except Project.DoesNotExist:
        return None
    if not user_can_view(user, project):
        return None
    return project


def visible_projects_qs(user):
    company = user.profile.company
    member_ids = ProjectMembership.objects.filter(
        user=user,
        is_active=True,
        project__company=company,
        project__project_kind=Project.KIND_FILE_GATE,
    ).values_list("project_id", flat=True)

    return (
        Project.objects.filter(
            company=company,
            project_kind=Project.KIND_FILE_GATE,
        )
        .filter(
            Q(id__in=member_ids)
            | Q(dms_config__visibility=DmsProjectConfig.VISIBILITY_COMPANY)
        )
        .select_related("dms_config", "owner")
        .distinct()
    )


def _role_for_row(user, project: Project) -> tuple[str | None, str]:
    membership = project_service.get_membership(user, project)
    if membership is not None:
        return membership.role, ROLE_LABELS.get(membership.role, membership.role)
    return None, ROLE_LABELS["company_viewer"]


def _version_label(project: Project) -> str:
    from apps.dms.source_profile.models import DmsMappingVersion

    draft = (
        DmsMappingVersion.objects.filter(
            project=project,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        .order_by("-version_number")
        .first()
    )
    if draft:
        return f"borrador v{draft.version_number}"

    config = getattr(project, "dms_config", None)
    if config and config.current_version_id:
        published = config.current_version
        if published:
            return f"v{published.version_number} publicada"
    return "Sin versión publicada"


def list_with_stats(user):
    projects = list(visible_projects_qs(user).order_by("-updated_at"))
    project_ids = [project.id for project in projects]

    member_counts: dict = {}
    if project_ids:
        for row in (
            ProjectMembership.objects.filter(
                project_id__in=project_ids,
                is_active=True,
            )
            .values("project_id")
            .annotate(count=Count("id"))
        ):
            member_counts[row["project_id"]] = row["count"]

    rows = []
    for project in projects:
        role_code, role_label = _role_for_row(user, project)
        config = getattr(project, "dms_config", None)
        visibility = config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
        rows.append(
            {
                "project": project,
                "role": role_code,
                "role_label": role_label,
                "visibility": visibility,
                "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
                "version_label": _version_label(project),
                "member_count": member_counts.get(project.id, 0),
                "is_pa": role_code == ProjectMembership.ROLE_PA,
            }
        )

    stats = {
        "total": len(rows),
        "active": sum(1 for row in rows if not row["project"].is_archived),
        "archived": sum(1 for row in rows if row["project"].is_archived),
        "pa_count": sum(1 for row in rows if row["role"] == ProjectMembership.ROLE_PA),
        "company_visible": sum(
            1
            for row in rows
            if row["visibility"] == DmsProjectConfig.VISIBILITY_COMPANY
        ),
    }
    return rows, stats


def default_posted() -> dict:
    return {
        "name": "",
        "slug": "",
        "description": "",
        "visibility": DmsProjectConfig.VISIBILITY_MEMBERS_ONLY,
    }


def posted_from_request(post) -> dict:
    return {
        "name": post.get("name", "").strip(),
        "slug": post.get("slug", "").strip().lower(),
        "description": post.get("description", "").strip(),
        "visibility": post.get("visibility", "").strip(),
    }


def validate_create_data(data: dict, company) -> dict[str, list[str]]:
    errors = project_service.validate_project_data(data, company)
    visibility = data.get("visibility", "")
    valid = {choice[0] for choice in DmsProjectConfig.VISIBILITY_CHOICES}
    if visibility not in valid:
        errors.setdefault("visibility", []).append("Seleccione una visibilidad válida.")
    return errors


def create_project(user, data: dict) -> OperationResult:
    profile = user.profile
    if profile.user_type != UserProfile.USER_FINAL:
        return OperationResult.failure(
            "forbidden",
            "Solo usuarios UF pueden crear proyectos FILE GATE.",
        )

    company = profile.company
    errors = validate_create_data(data, company)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    try:
        with transaction.atomic():
            project = Project.objects.create(
                company=company,
                name=data["name"],
                slug=data["slug"],
                description=data.get("description", ""),
                owner=user,
                project_kind=Project.KIND_FILE_GATE,
            )
            DmsProjectConfig.objects.create(
                project=project,
                visibility=data["visibility"],
            )
            ProjectMembership.objects.create(
                project=project,
                user=user,
                role=ProjectMembership.ROLE_PA,
                invited_by=None,
                is_active=True,
            )
    except IntegrityError:
        logger.exception("create_file_gate_project IntegrityError slug=%s", data.get("slug"))
        existing = project_service.find_project_by_slug(company, data.get("slug", ""))
        slug_msg = (
            project_service.slug_duplicate_message(existing)
            if existing is not None
            else "Ya existe un proyecto con este slug en su compañía."
        )
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"slug": [slug_msg]},
        )
    except Exception:
        logger.exception("create_file_gate_project unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Proyecto FILE GATE creado correctamente.",
        payload={"project": project},
    )


def get_hub_context(user, project: Project) -> dict:
    from apps.dms.file_intake.models import DmsExecutionJob
    from apps.file_gate.policy.services import gate_policy_service
    from apps.file_gate.report.services.validation_report_service import FINAL_JOB_STATUSES
    from apps.file_gate.schema.services import schema_wizard_service

    membership = project_service.get_membership(user, project)
    config = getattr(project, "dms_config", None)
    visibility = config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
    role_code, role_label = _role_for_row(user, project)
    member_count = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).count()

    schema_wizard = schema_wizard_service.get_wizard_context(project, membership)
    policy_wizard = gate_policy_service.get_wizard_context(project, membership)
    schema_complete = schema_wizard.steps_complete >= schema_wizard.steps_total
    policy_complete = policy_wizard.is_complete
    has_published = bool(config and config.current_version_id)

    final_jobs = DmsExecutionJob.objects.filter(
        project=project,
        status__in=FINAL_JOB_STATUSES,
    )
    run_complete = final_jobs.exists()
    report_complete = final_jobs.exclude(report_path="").exclude(report_path__isnull=True).exists()

    if schema_complete:
        schema_step_class = "is-done"
    else:
        schema_step_class = "is-active"

    if policy_complete:
        policy_step_class = "is-done"
    elif schema_complete:
        policy_step_class = "is-active"
    else:
        policy_step_class = "is-pending"

    if run_complete:
        run_step_class = "is-done"
    elif has_published:
        run_step_class = "is-active"
    else:
        run_step_class = "is-pending"

    if report_complete:
        report_step_class = "is-done"
    elif run_complete:
        report_step_class = "is-active"
    elif has_published:
        report_step_class = "is-pending"
    else:
        report_step_class = "is-pending"

    if run_complete:
        history_step_class = "is-done"
    elif has_published:
        history_step_class = "is-active"
    else:
        history_step_class = "is-pending"

    if has_published:
        bridge_step_class = "is-active"
    else:
        bridge_step_class = "is-pending"

    return {
        "visibility": visibility,
        "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == ProjectMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": project_service.user_can_manage_members(user, project),
        "schema_complete": schema_complete,
        "schema_step_class": schema_step_class,
        "schema_steps_complete": schema_wizard.steps_complete,
        "schema_steps_total": schema_wizard.steps_total,
        "policy_complete": policy_complete,
        "policy_step_class": policy_step_class,
        "policy_steps_complete": policy_wizard.steps_complete,
        "policy_steps_total": policy_wizard.steps_total,
        "policy_threshold_label": policy_wizard.threshold_label,
        "policy_collection_label": policy_wizard.collection_label,
        "continue_policy_url_name": policy_wizard.continue_step_url_name,
        "file_type_label": schema_wizard.file_type_label,
        "fields_count": schema_wizard.fields_count,
        "has_published_schema": has_published,
        "run_complete": run_complete,
        "run_step_class": run_step_class,
        "report_complete": report_complete,
        "report_step_class": report_step_class,
        "history_step_class": history_step_class,
        "bridge_step_class": bridge_step_class,
        "continue_schema_url_name": schema_wizard.continue_step_url_name,
        "version_label": schema_wizard.version_label,
        "can_publish": schema_complete and policy_complete,
    }
