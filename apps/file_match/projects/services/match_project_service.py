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
    if project.project_kind != Project.KIND_FILE_MATCH:
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
            project_kind=Project.KIND_FILE_MATCH,
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
        project__project_kind=Project.KIND_FILE_MATCH,
    ).values_list("project_id", flat=True)

    return (
        Project.objects.filter(
            company=company,
            project_kind=Project.KIND_FILE_MATCH,
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
    return "Sin definición publicada"


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
            "Solo usuarios UF pueden crear proyectos FILE MATCH.",
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
                project_kind=Project.KIND_FILE_MATCH,
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
        logger.exception("create_file_match_project IntegrityError slug=%s", data.get("slug"))
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
        logger.exception("create_file_match_project unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Proyecto FILE MATCH creado correctamente.",
        payload={"project": project},
    )


def get_hub_context(user, project: Project) -> dict:
    from apps.file_match.profile_a.services import profile_a_wizard_service
    from apps.file_match.profile_b.services import profile_b_wizard_service
    from apps.file_match.publish.services import publish_service

    membership = project_service.get_membership(user, project)
    config = getattr(project, "dms_config", None)
    visibility = config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
    role_code, role_label = _role_for_row(user, project)
    member_count = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).count()

    profile_a_wizard = profile_a_wizard_service.get_wizard_context(project, membership)
    profile_b_wizard = profile_b_wizard_service.get_wizard_context(project, membership)
    profile_a_complete = profile_a_wizard.steps_complete >= profile_a_wizard.steps_total
    profile_b_complete = profile_b_wizard.steps_complete >= profile_b_wizard.steps_total
    publish_ctx = publish_service.get_publish_context(project)
    has_published = publish_ctx["has_published_version"]

    pending = "is-pending"
    if profile_a_complete:
        profile_a_step_class = "is-done"
    else:
        profile_a_step_class = "is-active"

    if profile_b_complete:
        profile_b_step_class = "is-done"
    elif profile_a_complete:
        profile_b_step_class = "is-active"
    else:
        profile_b_step_class = pending

    from apps.file_match.rules.services import match_rules_persistence_service, match_rules_wizard_service

    rules_ctx = match_rules_wizard_service.get_rules_context(project, membership)
    rules_complete = rules_ctx.rules_complete
    if rules_complete:
        rules_step_class = "is-done"
        publish_step_class = "is-active" if not has_published else "is-done"
    elif profile_b_complete:
        rules_step_class = "is-active"
        publish_step_class = pending
    else:
        rules_step_class = pending
        publish_step_class = "is-done" if has_published else pending

    return {
        "visibility": visibility,
        "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == ProjectMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": project_service.user_can_manage_members(user, project),
        "profile_a_complete": profile_a_complete,
        "profile_a_step_class": profile_a_step_class,
        "profile_a_steps_complete": profile_a_wizard.steps_complete,
        "profile_a_steps_total": profile_a_wizard.steps_total,
        "file_type_label": profile_a_wizard.file_type_label,
        "fields_count": profile_a_wizard.fields_count,
        "continue_profile_a_url_name": profile_a_wizard.continue_step_url_name,
        "profile_b_complete": profile_b_complete,
        "profile_b_step_class": profile_b_step_class,
        "profile_b_steps_complete": profile_b_wizard.steps_complete,
        "profile_b_steps_total": profile_b_wizard.steps_total,
        "file_type_b_label": profile_b_wizard.file_type_label,
        "fields_b_count": profile_b_wizard.fields_count,
        "continue_profile_b_url_name": profile_b_wizard.continue_step_url_name,
        "rules_complete": rules_complete,
        "rules_step_class": rules_step_class,
        "rules_key_count": rules_ctx.key_count,
        "rules_compare_count": rules_ctx.compare_count,
        "continue_rules_url_name": rules_ctx.continue_section_url_name,
        "publish_step_class": publish_step_class,
        "run_step_class": "is-active" if has_published else pending,
        "history_step_class": "is-active" if has_published else pending,
        "has_published_version": has_published,
        "published_version_label": publish_ctx.get("published_version_label") or "—",
        "version_label": profile_a_wizard.version_label,
    }
