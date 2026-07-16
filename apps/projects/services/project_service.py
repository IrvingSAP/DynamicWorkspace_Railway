import logging
import re

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.projects.models import Project, ProjectMembership

logger = logging.getLogger(__name__)
User = get_user_model()

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

ROLE_LABELS = {
    ProjectMembership.ROLE_PA: "PA — Admin",
    ProjectMembership.ROLE_ED: "ED — Editor",
    ProjectMembership.ROLE_CO: "CO — Consulta",
    ProjectMembership.ROLE_GE: "GE — Generar",
}


def _optional_model(app_label: str, model_name: str):
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _record_count(project: Project) -> int:
    Record = _optional_model("records", "Record")
    if Record is None:
        return 0
    return Record.objects.filter(project=project, is_deleted=False).count()


def _field_count(project: Project) -> int:
    FieldDefinition = _optional_model("fields", "FieldDefinition")
    if FieldDefinition is None:
        return 0
    return FieldDefinition.objects.filter(project=project, is_active=True).count()


def get_membership(user, project: Project) -> ProjectMembership | None:
    try:
        return ProjectMembership.objects.get(
            project=project,
            user=user,
            is_active=True,
        )
    except ProjectMembership.DoesNotExist:
        return None


def user_can_view(user, project: Project) -> bool:
    profile = user.profile
    if project.company_id != profile.company_id:
        return False
    return get_membership(user, project) is not None


def user_can_manage_members(user, project: Project) -> bool:
    membership = get_membership(user, project)
    return membership is not None and membership.role == ProjectMembership.ROLE_PA


def get_project_for_user(user, slug: str) -> Project | None:
    profile = user.profile
    try:
        project = Project.objects.select_related("company", "owner").get(
            company=profile.company,
            slug=slug,
        )
    except Project.DoesNotExist:
        return None
    if get_membership(user, project) is None:
        return None
    return project


def memberships_for_user(user):
    profile = user.profile
    return (
        ProjectMembership.objects.filter(
            user=user,
            is_active=True,
            project__company=profile.company,
            project__project_kind=Project.KIND_WORKSPACE,
        )
        .select_related("project", "project__company")
    )


def list_with_stats(user):
    memberships = list(memberships_for_user(user).order_by("-project__updated_at"))
    project_ids = [membership.project_id for membership in memberships]

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
    for membership in memberships:
        project = membership.project
        rows.append(
            {
                "project": project,
                "role": membership.role,
                "record_count": _record_count(project),
                "member_count": member_counts.get(project.id, 0),
            }
        )

    projects = [row["project"] for row in rows]
    stats = {
        "total": len(projects),
        "active": sum(1 for project in projects if not project.is_archived),
        "archived": sum(1 for project in projects if project.is_archived),
        "pa_count": sum(1 for row in rows if row["role"] == ProjectMembership.ROLE_PA),
    }
    return rows, stats


def default_posted(project: Project | None = None) -> dict:
    if project is None:
        return {
            "name": "",
            "slug": "",
            "description": "",
        }
    return {
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
    }


def posted_from_request(post) -> dict:
    return {
        "name": post.get("name", "").strip(),
        "slug": post.get("slug", "").strip().lower(),
        "description": post.get("description", "").strip(),
    }


def validate_project_data(data: dict, company, project: Project | None = None) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    name = data.get("name", "").strip()
    if not name:
        errors.setdefault("name", []).append("Ingrese el nombre del proyecto.")
    elif len(name) > 200:
        errors.setdefault("name", []).append("Máximo 200 caracteres.")

    slug = data.get("slug", "").strip().lower()
    if not slug:
        errors.setdefault("slug", []).append("Ingrese el identificador URL (slug).")
    elif len(slug) > 220:
        errors.setdefault("slug", []).append("Máximo 220 caracteres.")
    elif not SLUG_RE.match(slug):
        errors.setdefault("slug", []).append(
            "Use solo letras minúsculas, números y guiones (sin espacios)."
        )
    else:
        qs = Project.objects.filter(company=company, slug=slug)
        if project is not None:
            qs = qs.exclude(pk=project.pk)
        if qs.exists():
            errors.setdefault("slug", []).append(
                "Ya existe un proyecto con este slug en su compañía."
            )

    description = data.get("description", "")
    if len(description) > 5000:
        errors.setdefault("description", []).append("La descripción es demasiado larga.")

    return errors


def create_project(user, data: dict) -> OperationResult:
    profile = user.profile
    if profile.user_type != UserProfile.USER_FINAL:
        return OperationResult.failure(
            "forbidden",
            "Solo usuarios UF pueden crear proyectos.",
        )

    company = profile.company
    errors = validate_project_data(data, company)
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
                project_kind=Project.KIND_WORKSPACE,
            )
            ProjectMembership.objects.create(
                project=project,
                user=user,
                role=ProjectMembership.ROLE_PA,
                invited_by=None,
                is_active=True,
            )
    except IntegrityError:
        logger.exception("create_project IntegrityError slug=%s", data.get("slug"))
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"slug": ["Ya existe un proyecto con este slug en su compañía."]},
        )
    except Exception:
        logger.exception("create_project unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Proyecto creado correctamente.",
        payload={"project": project},
    )


def get_detail_context(project: Project, membership: ProjectMembership) -> dict:
    member_count = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).count()
    return {
        "role": membership.role,
        "is_pa": membership.role == ProjectMembership.ROLE_PA,
        "record_count": _record_count(project),
        "field_count": _field_count(project),
        "member_count": member_count,
    }


def list_members(project: Project):
    return (
        ProjectMembership.objects.filter(project=project)
        .select_related("user", "invited_by")
        .order_by("created_at")
    )


def invitable_users(project: Project, actor):
    active_user_ids = ProjectMembership.objects.filter(
        project=project,
        is_active=True,
    ).values_list("user_id", flat=True)
    return (
        UserProfile.objects.filter(
            company=project.company,
            user_type=UserProfile.USER_FINAL,
            status=UserProfile.STATUS_ACTIVE,
        )
        .exclude(user_id__in=active_user_ids)
        .exclude(user_id=actor.id)
        .select_related("user")
        .order_by("user__username")
    )


def _count_active_pa(project: Project, exclude_membership_id=None) -> int:
    qs = ProjectMembership.objects.filter(
        project=project,
        role=ProjectMembership.ROLE_PA,
        is_active=True,
    )
    if exclude_membership_id is not None:
        qs = qs.exclude(pk=exclude_membership_id)
    return qs.count()


def invite_member(actor, project: Project, data: dict) -> OperationResult:
    if not user_can_manage_members(actor, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para gestionar miembros de este proyecto.",
        )

    user_id = data.get("user_id", "").strip()
    role_raw = data.get("role", "").strip()
    from apps.dms.catalogs.services.permission_package_service import resolve_role_code

    role = resolve_role_code(role_raw) or ""

    errors: dict[str, list[str]] = {}
    if not user_id:
        errors.setdefault("user", []).append("Seleccione un usuario.")
    if not role:
        errors.setdefault("role", []).append("Seleccione un rol válido.")
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del formulario.",
            errors=errors,
        )

    try:
        profile = UserProfile.objects.select_related("user").get(
            user_id=user_id,
            company=project.company,
            user_type=UserProfile.USER_FINAL,
        )
    except (UserProfile.DoesNotExist, ValueError):
        return OperationResult.failure(
            "invalid_user",
            "El usuario seleccionado no es válido para este proyecto.",
            errors={"user": ["Usuario no disponible en su compañía."]},
        )

    if ProjectMembership.objects.filter(
        project=project,
        user=profile.user,
        is_active=True,
    ).exists():
        return OperationResult.failure(
            "duplicate",
            "El usuario ya es miembro activo del proyecto.",
            errors={"user": ["Ya tiene membresía activa."]},
        )

    try:
        membership, created = ProjectMembership.objects.get_or_create(
            project=project,
            user=profile.user,
            defaults={
                "role": role,
                "invited_by": actor,
                "is_active": True,
            },
        )
        if not created:
            membership.role = role
            membership.invited_by = actor
            membership.is_active = True
            membership.save()
    except Exception:
        logger.exception("invite_member unexpected project=%s user=%s", project.pk, user_id)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al autorizar el miembro.",
        )

    return OperationResult.success(
        user_message=f"Miembro «{profile.user.username}» autorizado correctamente.",
    )


def update_member_role(actor, project: Project, membership_id: str, role: str) -> OperationResult:
    if not user_can_manage_members(actor, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para gestionar miembros de este proyecto.",
        )

    from apps.dms.catalogs.services.permission_package_service import resolve_role_code

    resolved = resolve_role_code(role)
    if not resolved:
        return OperationResult.failure(
            "validation_form",
            "Rol no válido.",
        )
    role = resolved

    try:
        membership = ProjectMembership.objects.get(pk=membership_id, project=project)
    except (ProjectMembership.DoesNotExist, ValueError):
        return OperationResult.failure(
            "not_found",
            "Membresía no encontrada.",
        )

    if membership.user_id == project.owner_id and role != ProjectMembership.ROLE_PA:
        return OperationResult.failure(
            "business_rule",
            "El creador del proyecto debe conservar el rol de administrador (PA).",
        )

    if (
        membership.role == ProjectMembership.ROLE_PA
        and role != ProjectMembership.ROLE_PA
        and membership.is_active
        and _count_active_pa(project, exclude_membership_id=membership.pk) == 0
    ):
        return OperationResult.failure(
            "business_rule",
            "Debe haber al menos un administrador (PA) activo en el proyecto.",
        )

    membership.role = role
    membership.save(update_fields=["role"])
    return OperationResult.success(
        user_message=f"Rol de «{membership.user.username}» actualizado.",
    )


def set_member_active(
    actor,
    project: Project,
    membership_id: str,
    *,
    active: bool,
) -> OperationResult:
    if not user_can_manage_members(actor, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para gestionar miembros de este proyecto.",
        )

    try:
        membership = ProjectMembership.objects.get(pk=membership_id, project=project)
    except (ProjectMembership.DoesNotExist, ValueError):
        return OperationResult.failure(
            "not_found",
            "Membresía no encontrada.",
        )

    if membership.user_id == project.owner_id and not active:
        return OperationResult.failure(
            "business_rule",
            "No puede revocar al creador del proyecto.",
        )

    if (
        not active
        and membership.role == ProjectMembership.ROLE_PA
        and membership.is_active
        and _count_active_pa(project, exclude_membership_id=membership.pk) == 0
    ):
        return OperationResult.failure(
            "business_rule",
            "Debe haber al menos un administrador (PA) activo en el proyecto.",
        )

    membership.is_active = active
    membership.save(update_fields=["is_active"])

    username = membership.user.username
    if active:
        return OperationResult.success(
            user_message=f"Membresía de «{username}» reactivada.",
        )
    return OperationResult.success(
        user_message=f"Membresía de «{username}» revocada.",
    )
