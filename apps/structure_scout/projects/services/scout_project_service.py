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

DEFAULT_DESCRIPTION = (
    "Proyecto STRUCTURE SCOUT: exploración de muestra → borrador de estructura."
)


def user_can_view(user, project: Project) -> bool:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
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
            project_kind=Project.KIND_STRUCTURE_SCOUT,
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
        project__project_kind=Project.KIND_STRUCTURE_SCOUT,
    ).values_list("project_id", flat=True)

    return (
        Project.objects.filter(
            company=company,
            project_kind=Project.KIND_STRUCTURE_SCOUT,
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
        visibility = (
            config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
        )
        rows.append(
            {
                "project": project,
                "role": role_code,
                "role_label": role_label,
                "visibility": visibility,
                "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
                "exploration_label": _exploration_label(project),
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
            "Solo usuarios UF pueden crear proyectos del Explorador de estructura.",
        )

    company = profile.company
    errors = validate_create_data(data, company)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    description = data.get("description", "").strip() or DEFAULT_DESCRIPTION

    try:
        with transaction.atomic():
            project = Project.objects.create(
                company=company,
                name=data["name"],
                slug=data["slug"],
                description=description,
                owner=user,
                project_kind=Project.KIND_STRUCTURE_SCOUT,
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
        logger.exception(
            "create_structure_scout_project IntegrityError slug=%s", data.get("slug")
        )
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
        logger.exception("create_structure_scout_project unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Proyecto Explorador de estructura creado correctamente.",
        payload={"project": project},
    )


def _exploration_label(project: Project) -> str:
    from apps.structure_scout.sample.services import sample_upload_service

    sample = sample_upload_service.latest_sample(project)
    if sample is None:
        return "Sin exploración"
    return sample.original_filename


def get_hub_context(user, project: Project) -> dict:
    """Hub state for lifecycle including history (M7)."""
    from apps.structure_scout.apply.services import apply_target_service
    from apps.structure_scout.detect.services import detect_pattern_service
    from apps.structure_scout.draft.services import save_draft_service
    from apps.structure_scout.fields.services import propose_fields_service
    from apps.structure_scout.history.services import history_service
    from apps.structure_scout.sample.services import sample_upload_service

    role_code, role_label = _role_for_row(user, project)
    config = getattr(project, "dms_config", None)
    visibility = (
        config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
    )
    member_count = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).count()

    has_sample = sample_upload_service.latest_sample(project) is not None
    has_detection = detect_pattern_service.has_confirmed_detection(project)
    has_fields = propose_fields_service.has_confirmed_fields(project)
    has_draft = save_draft_service.has_current_draft(project)
    has_apply = apply_target_service.has_successful_apply(project)
    has_history = history_service.has_history_events(project)
    pending = "is-pending"
    sample_step_class = "is-done" if has_sample else "is-active"
    if has_apply:
        detect_step_class = "is-done"
        fields_step_class = "is-done"
        draft_step_class = "is-done"
        apply_step_class = "is-done"
        history_step_class = "is-done" if has_history else "is-active"
    elif has_draft:
        detect_step_class = "is-done"
        fields_step_class = "is-done"
        draft_step_class = "is-done"
        apply_step_class = "is-active"
        history_step_class = "is-done" if has_history else pending
    elif has_fields:
        detect_step_class = "is-done"
        fields_step_class = "is-done"
        draft_step_class = "is-active"
        apply_step_class = pending
        history_step_class = pending
    elif has_detection:
        detect_step_class = "is-done"
        fields_step_class = "is-active"
        draft_step_class = pending
        apply_step_class = pending
        history_step_class = pending
    elif has_sample:
        detect_step_class = "is-active"
        fields_step_class = pending
        draft_step_class = pending
        apply_step_class = pending
        history_step_class = pending
    else:
        detect_step_class = pending
        fields_step_class = pending
        draft_step_class = pending
        apply_step_class = pending
        history_step_class = pending

    return {
        "visibility": visibility,
        "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == ProjectMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": project_service.user_can_manage_members(user, project),
        "exploration_label": _exploration_label(project),
        "draft_status_label": save_draft_service.draft_status_label(project),
        "sample_step_class": sample_step_class,
        "detect_step_class": detect_step_class,
        "fields_step_class": fields_step_class,
        "draft_step_class": draft_step_class,
        "apply_step_class": apply_step_class,
        "history_step_class": history_step_class,
        "has_sample": has_sample,
        "has_detection": has_detection,
        "has_fields": has_fields,
        "has_draft": has_draft,
        "has_apply": has_apply,
        "has_history": has_history,
        "modules_pending_note": "",
    }
