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
    if project.project_kind != Project.KIND_DMS:
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
            project_kind=Project.KIND_DMS,
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
        project__project_kind=Project.KIND_DMS,
    ).values_list("project_id", flat=True)

    return (
        Project.objects.filter(
            company=company,
            project_kind=Project.KIND_DMS,
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
                "last_execution": "—",
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
            "Solo usuarios UF pueden crear proyectos DMS.",
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
                project_kind=Project.KIND_DMS,
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
        logger.exception("create_dms_project IntegrityError slug=%s", data.get("slug"))
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"slug": ["Ya existe un proyecto con este slug en su compañía."]},
        )
    except Exception:
        logger.exception("create_dms_project unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Proyecto DMS creado correctamente.",
        payload={"project": project},
    )


def get_hub_context(user, project: Project) -> dict:
    membership = project_service.get_membership(user, project)
    config = getattr(project, "dms_config", None)
    visibility = config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
    role_code, role_label = _role_for_row(user, project)
    member_count = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).count()

    from apps.dms.field_mapping.services import field_mapping_service
    from apps.dms.file_intake.models import DmsExecutionJob, DmsSampleFile
    from apps.dms.file_intake.services import file_intake_persistence_service
    from apps.dms.source_profile.services import source_profile_service
    from apps.dms.target_profile.services import target_profile_service
    from apps.dms.transform_rules.services import transform_rules_service

    source_wizard = source_profile_service.get_wizard_context(project, membership)
    target_wizard = target_profile_service.get_wizard_context(project, membership)
    mapping_editor = field_mapping_service.get_editor_context(project, membership)
    rules_editor = transform_rules_service.get_editor_context(project, membership)
    source_complete = source_wizard.steps_complete >= source_wizard.steps_total
    target_complete = target_wizard.steps_complete >= target_wizard.steps_total
    mapping_complete = bool(mapping_editor.get("is_complete"))
    rules_complete = bool(rules_editor.get("is_complete"))
    mapping_count = mapping_editor["hub"].mappings_count
    unmapped_required = mapping_editor["hub"].unmapped_required
    rules_step_count = rules_editor["hub"].total_steps
    rules_with_steps = rules_editor["hub"].pipelines_with_steps

    has_published = file_intake_persistence_service.get_published_version(project) is not None
    samples_count = DmsSampleFile.objects.filter(project=project).count()
    jobs_uploaded_count = DmsExecutionJob.objects.filter(
        project=project, status=DmsExecutionJob.STATUS_UPLOADED
    ).count()
    intake_ready = has_published and jobs_uploaded_count > 0

    # Fase B: done | active (siguiente pendiente) | pending
    if source_complete:
        source_step_class = "is-done"
    else:
        source_step_class = "is-active"

    if target_complete:
        target_step_class = "is-done"
    elif source_complete:
        target_step_class = "is-active"
    else:
        target_step_class = "is-pending"

    if mapping_complete:
        mapping_step_class = "is-done"
    elif source_complete and target_complete:
        mapping_step_class = "is-active"
    else:
        mapping_step_class = "is-pending"

    if rules_complete:
        rules_step_class = "is-done"
    elif mapping_complete:
        rules_step_class = "is-active"
    else:
        rules_step_class = "is-pending"

    if has_published:
        publish_step_class = "is-done"
    elif rules_complete:
        publish_step_class = "is-active"
    else:
        publish_step_class = "is-pending"

    if intake_ready:
        execute_step_class = "is-done"
    elif has_published:
        execute_step_class = "is-active"
    else:
        execute_step_class = "is-pending"

    return {
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == ProjectMembership.ROLE_PA,
        "can_manage_members": project_service.user_can_manage_members(user, project),
        "visibility": visibility,
        "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
        "version_label": _version_label(project),
        "member_count": member_count,
        "has_membership": membership is not None,
        "source_complete": source_complete,
        "target_complete": target_complete,
        "mapping_complete": mapping_complete,
        "rules_complete": rules_complete,
        "has_published_version": has_published,
        "samples_count": samples_count,
        "jobs_uploaded_count": jobs_uploaded_count,
        "intake_ready": intake_ready,
        "source_steps_complete": source_wizard.steps_complete,
        "target_steps_complete": target_wizard.steps_complete,
        "source_file_type_label": source_wizard.file_type_label,
        "target_file_type_label": target_wizard.file_type_label,
        "source_fields_count": source_wizard.fields_count,
        "target_fields_count": target_wizard.fields_count,
        "mapping_count": mapping_count,
        "unmapped_required": unmapped_required,
        "rules_step_count": rules_step_count,
        "rules_with_steps": rules_with_steps,
        "source_step_class": source_step_class,
        "target_step_class": target_step_class,
        "mapping_step_class": mapping_step_class,
        "rules_step_class": rules_step_class,
        "publish_step_class": publish_step_class,
        "execute_step_class": execute_step_class,
    }
