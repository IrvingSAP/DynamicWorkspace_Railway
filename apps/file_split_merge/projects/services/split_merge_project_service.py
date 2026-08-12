"""Ciclo de proyecto File Split/Merge (M1)."""

from __future__ import annotations

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
    "Proyecto File Split/Merge: partición o consolidación de archivos."
)

MSG_NO_ACCESS = "No tiene acceso a este proyecto File Split/Merge."
MSG_UF_ONLY = "Solo usuarios UF pueden crear proyectos File Split/Merge."
MSG_CREATED = "Proyecto File Split/Merge creado correctamente."
MSG_PA_ONLY = "Solo el administrador del proyecto (PA) puede gestionar miembros."
MSG_WRONG_KIND = "Este proyecto no es de tipo File Split/Merge."


def user_can_view(user, project: Project) -> bool:
    if project.project_kind != Project.KIND_FILE_SPLIT_MERGE:
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
            project_kind=Project.KIND_FILE_SPLIT_MERGE,
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
        project__project_kind=Project.KIND_FILE_SPLIT_MERGE,
    ).values_list("project_id", flat=True)

    return (
        Project.objects.filter(
            company=company,
            project_kind=Project.KIND_FILE_SPLIT_MERGE,
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


def _definition_label(project: Project) -> str:
    """Resumen listado — perfil borrador / publicada."""
    from apps.file_split_merge.profile.services import profile_wizard_service

    wizard = profile_wizard_service.get_wizard_context(project, None)
    if wizard.fields_count or (wizard.file_type_label and wizard.file_type_label != "—"):
        return (
            f"{wizard.version_label} · {wizard.file_type_label} · "
            f"{wizard.fields_count} campos"
        )
    config = getattr(project, "dms_config", None)
    if config and config.current_version_id:
        published = config.current_version
        if published:
            return f"v{published.version_number} publicada"
    return "Sin perfil de lectura"


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
                "definition_label": _definition_label(project),
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
        return OperationResult.failure("forbidden", MSG_UF_ONLY)

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
                project_kind=Project.KIND_FILE_SPLIT_MERGE,
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
            "create_file_split_merge_project IntegrityError slug=%s",
            data.get("slug"),
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
        logger.exception("create_file_split_merge_project unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message=MSG_CREATED,
        payload={"project": project},
    )


def get_hub_context(user, project: Project) -> dict:
    """Hub: perfil M2 + reglas M3 + publicar M4; M5–M6 pendientes."""
    from apps.file_split_merge.profile.services import profile_wizard_service
    from apps.file_split_merge.publish.services import split_merge_publish_service
    from apps.file_split_merge.rules.services import (
        split_merge_rules_catalog as catalog,
    )
    from apps.file_split_merge.rules.services import (
        split_merge_rules_persistence_service as rules_svc,
    )

    membership = project_service.get_membership(user, project)
    config = getattr(project, "dms_config", None)
    visibility = config.visibility if config else DmsProjectConfig.VISIBILITY_MEMBERS_ONLY
    role_code, role_label = _role_for_row(user, project)
    member_count = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).count()

    publish = split_merge_publish_service.get_publish_context(project)
    has_published = publish["has_published_version"]
    wizard = profile_wizard_service.get_wizard_context(project, membership)
    profile_complete = wizard.steps_complete >= wizard.steps_total
    rules_hub = rules_svc.get_hub_context(project)
    rules_complete = bool(rules_hub.get("rules_complete"))
    operation = rules_hub.get("operation")
    operation_label = rules_hub.get("operation_label") or "—"
    pending = "is-pending"

    from apps.file_split_merge.models import SplitMergeJob
    from apps.file_split_merge.run.services import sm_run_service

    last_job_label = sm_run_service.last_job_label(project)
    run_complete = SplitMergeJob.objects.filter(
        project=project,
        status=SplitMergeJob.STATUS_COMPLETED,
        dry_run=False,
    ).exists()

    if profile_complete:
        profile_step_class = "is-done"
    else:
        profile_step_class = "is-active"

    if rules_complete:
        rules_step_class = "is-done"
    elif profile_complete:
        rules_step_class = "is-active"
    else:
        rules_step_class = pending

    if has_published:
        publish_step_class = "is-done"
        if run_complete:
            run_step_class = "is-done"
            history_step_class = "is-active"
        else:
            run_step_class = "is-active"
            history_step_class = "is-active"
    elif rules_complete and profile_complete:
        publish_step_class = "is-active"
        run_step_class = pending
        history_step_class = pending
    else:
        publish_step_class = pending
        run_step_class = pending
        history_step_class = pending

    draft_label = wizard.version_label
    if wizard.file_type_label and wizard.file_type_label != "—":
        draft_label = (
            f"{wizard.version_label} · {wizard.file_type_label} · "
            f"{wizard.fields_count} campos"
        )
    if operation:
        draft_label = (
            f"{draft_label} · {catalog.OPERATION_LABELS.get(operation, operation)}"
        )
    if rules_hub.get("rules_count"):
        draft_label = (
            f"{draft_label} · {rules_hub['rules_enabled_count']}/"
            f"{rules_hub['rules_count']} reglas ON"
        )

    modules_pending_note = (
        "Defina el perfil de lectura (4 pasos) y luego las reglas Split o Merge. "
        "Luego publique para habilitar Ejecutar."
    )
    if profile_complete and not rules_complete:
        modules_pending_note = (
            "Perfil completo. Defina operación y reglas Split/Merge; "
            "luego publique para habilitar Ejecutar."
        )
    elif rules_complete and not has_published:
        modules_pending_note = (
            "Perfil y reglas listos. Publique una versión "
            "para habilitar Ejecutar e Historial."
        )
    elif has_published and not run_complete:
        modules_pending_note = (
            "Versión publicada. Ejecute Split/Merge con un archivo (o varios en Merge)."
        )
    elif has_published:
        modules_pending_note = (
            "Hay corridas registradas. Puede ejecutar de nuevo o revisar el historial."
        )

    return {
        "visibility": visibility,
        "visibility_label": VISIBILITY_LABELS.get(visibility, visibility),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == ProjectMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": project_service.user_can_manage_members(user, project),
        "draft_label": draft_label,
        "published_label": publish["published_version_label"],
        "operation_label": operation_label if operation else "—",
        "last_job_label": last_job_label,
        "has_published_version": has_published,
        "profile_complete": profile_complete,
        "file_type_label": wizard.file_type_label,
        "fields_count": wizard.fields_count,
        "continue_step_url_name": wizard.continue_step_url_name,
        "rules_complete": rules_complete,
        "rules_enabled_count": rules_hub.get("rules_enabled_count", 0),
        "rules_count": rules_hub.get("rules_count", 0),
        "run_complete": run_complete,
        "can_open_publish": profile_complete,
        "can_open_run": has_published,
        "can_open_history": has_published,
        "profile_step_class": profile_step_class,
        "rules_step_class": rules_step_class,
        "publish_step_class": publish_step_class,
        "run_step_class": run_step_class,
        "history_step_class": history_step_class,
        "modules_pending_note": modules_pending_note,
        "membership": membership,
    }
