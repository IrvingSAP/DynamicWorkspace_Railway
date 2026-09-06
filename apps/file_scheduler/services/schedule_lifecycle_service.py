"""M1 File Scheduler: ciclo de vida del plan (listado, alta, hub, miembros, auditoría CRUD)."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.dms.catalogs.services.permission_package_service import resolve_role_code
from apps.file_pipeline.models import PipelineDefinition
from apps.file_scheduler.models import (
    Schedule,
    ScheduleAuditEvent,
    ScheduleMembership,
    ScheduleTick,
)
from apps.file_scheduler.services import schedule_cron as cron_svc
from apps.file_scheduler.services import schedule_dependency as dep_svc
from apps.file_scheduler.services import schedule_errors as err
from apps.file_scheduler.services import schedule_target as target_svc
from apps.file_scheduler.services import schedule_tick as tick_svc
from apps.projects.services.project_service import SLUG_RE, find_project_by_slug, slug_duplicate_message

logger = logging.getLogger(__name__)

VISIBILITY_LABELS = {
    Schedule.VISIBILITY_COMPANY: "Público",
    Schedule.VISIBILITY_MEMBERS_ONLY: "Privado",
}

STATUS_LABELS = {
    Schedule.STATUS_ACTIVE: "Activo",
    Schedule.STATUS_IN_PROGRESS: "En proceso",
    Schedule.STATUS_INACTIVE: "Inactivo",
    Schedule.STATUS_ARCHIVED: "Archivado",
}

ROLE_LABELS = {
    ScheduleMembership.ROLE_PA: "PA — Admin",
    ScheduleMembership.ROLE_ED: "ED — Editor",
    ScheduleMembership.ROLE_GE: "GE — Ejecutor",
    ScheduleMembership.ROLE_CO: "CO — Consulta",
    "company_viewer": "CO — Consulta (compañía)",
}

DEFAULT_DESCRIPTION = "Plan de File Scheduler: dispara un Job o un pipeline en un horario."

MSG_NO_ACCESS = "No tiene acceso a este plan."
MSG_CREATE_FORBIDDEN = (
    "Solo usuarios US con rol PA o ED de esta compañía pueden crear planes."
)
MSG_CREATED = err.MSG_CREATED
MSG_UPDATED = "Plan actualizado."
MSG_PAUSED = err.MSG_PAUSED_OK
MSG_ARCHIVED = err.MSG_ARCHIVED
MSG_PA_ONLY = "Solo el administrador del plan (PA) puede gestionar miembros."
MSG_FORBIDDEN = err.MSG_FORBIDDEN
MSG_RESUME_BLOCKED = err.MSG_INCOMPLETE
MSG_PAUSE_BLOCKED = "Solo se puede pausar un plan Activo."
MSG_ARCHIVE_BLOCKED = "No se puede archivar este plan."
MSG_COMPANY_INACTIVE = "La compañía no está activa."
MSG_MODULE_PENDING = "Este módulo se implementará en una fase posterior."
MSG_VALIDATION = "Revise los datos marcados; no se pudo guardar."
MSG_UNEXPECTED = "Ocurrió un error al guardar. Si persiste, contacte al administrador."
MSG_SLUG_TAKEN = err.MSG_SLUG_TAKEN

MSG_CRON_SAVED = err.MSG_CRON_SAVED
MSG_CRON_FORBIDDEN = "No tiene permiso para editar la programación de este plan."
MSG_TIMEZONE_INVALID = err.MSG_TIMEZONE_INVALID
MSG_TARGET_SAVED = err.MSG_TARGET_SAVED
MSG_ACTIVATED = "Plan marcado como Activo."
MSG_OVERLAP_SAVED = err.MSG_OVERLAP_SAVED
MSG_OVERLAP_FORBIDDEN = "No tiene permiso para editar la política de solape de este plan."
MSG_OVERLAP_INVALID = "Seleccione una política de solape."
MSG_DEPENDENCY_SAVED = err.MSG_TRIGGER_SAVED

SEARCH_LIMIT = 20
SEARCH_MIN = 2

PENDING_MODULES = {}


def user_can_create(user) -> bool:
    try:
        profile = user.profile
    except Exception:
        return False
    if profile.user_type != UserProfile.USER_SYSTEM:
        return False
    if not profile.company_id or not profile.company.is_active:
        return False
    return True


def get_membership(user, schedule: Schedule) -> ScheduleMembership | None:
    return (
        ScheduleMembership.objects.filter(
            schedule=schedule,
            user=user,
            is_active=True,
        )
        .select_related("user")
        .first()
    )


def user_can_view(user, schedule: Schedule) -> bool:
    if not getattr(user, "profile", None):
        return False
    if schedule.company_id != user.profile.company_id:
        return False
    if not schedule.company.is_active:
        return False
    if get_membership(user, schedule) is not None:
        return True
    return schedule.visibility == Schedule.VISIBILITY_COMPANY


def user_can_edit(user, schedule: Schedule) -> bool:
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return False
    membership = get_membership(user, schedule)
    return membership is not None and membership.role in {
        ScheduleMembership.ROLE_PA,
        ScheduleMembership.ROLE_ED,
    }


def user_can_archive(user, schedule: Schedule) -> bool:
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return False
    membership = get_membership(user, schedule)
    return membership is not None and membership.role == ScheduleMembership.ROLE_PA


def user_can_manage_members(user, schedule: Schedule) -> bool:
    return user_can_archive(user, schedule)


def _record_event(schedule: Schedule, event: str, actor, payload: dict | None = None):
    body = dict(payload or {})
    body.setdefault("company_id", str(schedule.company_id))
    body.setdefault("schedule_id", str(schedule.id))
    ScheduleAuditEvent.objects.create(
        company_id=schedule.company_id,
        schedule=schedule,
        event=event,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        payload=body,
    )


def get_schedule_for_user(user, slug: str) -> Schedule | None:
    try:
        schedule = Schedule.objects.select_related("company", "owner").get(
            company=user.profile.company,
            slug=slug,
        )
    except Schedule.DoesNotExist:
        return None
    if not user_can_view(user, schedule):
        return None
    return schedule


def visible_qs(user):
    company = user.profile.company
    if not company.is_active:
        return Schedule.objects.none()
    member_ids = ScheduleMembership.objects.filter(
        user=user,
        is_active=True,
        schedule__company=company,
    ).values_list("schedule_id", flat=True)
    return (
        Schedule.objects.filter(company=company)
        .filter(
            Q(id__in=member_ids)
            | Q(visibility=Schedule.VISIBILITY_COMPANY)
        )
        .select_related("owner", "company")
        .distinct()
    )


def _role_for_row(user, schedule: Schedule) -> tuple[str | None, str]:
    membership = get_membership(user, schedule)
    if membership is not None:
        return membership.role, ROLE_LABELS.get(membership.role, membership.role)
    return None, ROLE_LABELS["company_viewer"]


def list_with_stats(user):
    qs = visible_qs(user).order_by("-updated_at")
    rows = []
    for schedule in qs:
        role_code, role_label = _role_for_row(user, schedule)
        archived = schedule.status == Schedule.STATUS_ARCHIVED
        rows.append(
            {
                "schedule": schedule,
                "role": role_code,
                "role_label": role_label,
                "visibility": schedule.visibility,
                "visibility_label": VISIBILITY_LABELS.get(
                    schedule.visibility, schedule.visibility
                ),
                "status": schedule.status,
                "status_label": STATUS_LABELS.get(schedule.status, schedule.status),
                "next_tick_label": cron_svc.first_tick_label(schedule),
                "last_tick_label": tick_svc.last_tick_label(schedule),
                "can_edit": user_can_edit(user, schedule) and not archived,
                "can_manage_members": user_can_manage_members(user, schedule)
                and not archived,
                "can_archive": user_can_archive(user, schedule) and not archived,
                "can_pause": user_can_edit(user, schedule)
                and schedule.status == Schedule.STATUS_ACTIVE,
                "can_resume": user_can_edit(user, schedule)
                and schedule.status == Schedule.STATUS_INACTIVE,
            }
        )
    operative = [r for r in rows if r["status"] != Schedule.STATUS_ARCHIVED]
    stats = {
        "total": len(operative),
        "active": sum(1 for r in operative if r["status"] == Schedule.STATUS_ACTIVE),
        "in_progress": sum(
            1 for r in operative if r["status"] == Schedule.STATUS_IN_PROGRESS
        ),
        "inactive": sum(
            1 for r in operative if r["status"] == Schedule.STATUS_INACTIVE
        ),
    }
    return rows, stats


def default_posted() -> dict:
    return {
        "name": "",
        "slug": "",
        "description": "",
        "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
    }


def posted_from_request(post) -> dict:
    return {
        "name": post.get("name", "").strip(),
        "slug": post.get("slug", "").strip().lower(),
        "description": post.get("description", "").strip(),
        "visibility": post.get("visibility", "").strip(),
    }


def validate_identity(data: dict, company, *, schedule: Schedule | None = None) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    name = data.get("name", "").strip()
    if not name:
        errors.setdefault("name", []).append("Ingrese el nombre del plan.")
    elif len(name) > 200:
        errors.setdefault("name", []).append("Máximo 200 caracteres.")

    if schedule is None:
        slug = data.get("slug", "").strip().lower()
        if not slug:
            errors.setdefault("slug", []).append("Ingrese el identificador (código).")
        elif len(slug) > 220:
            errors.setdefault("slug", []).append("Máximo 220 caracteres.")
        elif not SLUG_RE.match(slug):
            errors.setdefault("slug", []).append(
                "Use solo letras minúsculas, números y guiones (sin espacios)."
            )
        else:
            existing_project = find_project_by_slug(company, slug)
            if existing_project is not None:
                errors.setdefault("slug", []).append(
                    slug_duplicate_message(existing_project)
                )
            elif PipelineDefinition.objects.filter(company=company, slug=slug).exists():
                errors.setdefault("slug", []).append(
                    "Ya existe un pipeline con este código en su compañía."
                )
            elif Schedule.objects.filter(company=company, slug=slug).exists():
                errors.setdefault("slug", []).append(MSG_SLUG_TAKEN)

    description = data.get("description", "")
    if len(description) > 5000:
        errors.setdefault("description", []).append("La descripción es demasiado larga.")

    visibility = data.get("visibility", "")
    valid_vis = {c[0] for c in Schedule.VISIBILITY_CHOICES}
    if visibility not in valid_vis:
        errors.setdefault("visibility", []).append("Seleccione una visibilidad válida.")
    return errors


def create_schedule(user, data: dict) -> OperationResult:
    if not user_can_create(user):
        return OperationResult.failure("schedule_forbidden", MSG_CREATE_FORBIDDEN)

    company = user.profile.company
    errors = validate_identity(data, company)
    if errors:
        missing = (not data.get("name", "").strip()) or (not data.get("slug", "").strip())
        if missing:
            return OperationResult.failure(
                err.VALIDATION_REQUIRED, err.MSG_REQUIRED, errors=errors
            )
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    description = data.get("description", "").strip() or DEFAULT_DESCRIPTION

    try:
        with transaction.atomic():
            schedule = Schedule.objects.create(
                company=company,
                name=data["name"],
                slug=data["slug"],
                description=description,
                owner=user,
                visibility=data["visibility"],
                status=Schedule.STATUS_IN_PROGRESS,
            )
            ScheduleMembership.objects.create(
                schedule=schedule,
                user=user,
                role=ScheduleMembership.ROLE_PA,
                invited_by=None,
                is_active=True,
            )
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_CREATED,
                user,
                {
                    "slug": schedule.slug,
                    "name": schedule.name,
                    "visibility": schedule.visibility,
                    "status": schedule.status,
                },
            )
    except IntegrityError:
        logger.exception("create_schedule IntegrityError slug=%s", data.get("slug"))
        return OperationResult.failure(
            "schedule_slug_taken",
            MSG_SLUG_TAKEN,
            errors={"slug": [MSG_SLUG_TAKEN]},
        )
    except Exception:
        logger.exception("create_schedule unexpected")
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(
        user_message=MSG_CREATED,
        payload={"schedule": schedule},
    )


def update_schedule(user, schedule: Schedule, data: dict) -> OperationResult:
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)

    errors = validate_identity(data, schedule.company, schedule=schedule)
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    description = data.get("description", "").strip()
    changed = {}
    if schedule.name != data["name"]:
        changed["name"] = {"from": schedule.name, "to": data["name"]}
        schedule.name = data["name"]
    if schedule.description != description:
        changed["description"] = True
        schedule.description = description
    if schedule.visibility != data["visibility"]:
        changed["visibility"] = {
            "from": schedule.visibility,
            "to": data["visibility"],
        }
        schedule.visibility = data["visibility"]

    if not changed:
        return OperationResult.success(user_message=MSG_UPDATED, payload={"schedule": schedule})

    try:
        with transaction.atomic():
            schedule.save(update_fields=["name", "description", "visibility", "updated_at"])
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {"fields": list(changed.keys()), "diff": changed},
            )
    except Exception:
        logger.exception("update_schedule unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(user_message=MSG_UPDATED, payload={"schedule": schedule})


def definition_ready_for_active(schedule: Schedule) -> bool:
    if not schedule.target_complete:
        return False
    if schedule.trigger_mode == Schedule.TRIGGER_DEPENDENCY:
        return bool(schedule.dependency_complete)
    return bool(schedule.programming_complete)


def pause_schedule(user, schedule: Schedule) -> OperationResult:
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if schedule.status != Schedule.STATUS_ACTIVE:
        return OperationResult.failure("validation_form", MSG_PAUSE_BLOCKED)
    try:
        with transaction.atomic():
            schedule.status = Schedule.STATUS_INACTIVE
            schedule.save(update_fields=["status", "updated_at"])
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_PAUSED,
                user,
                {"from": Schedule.STATUS_ACTIVE, "to": Schedule.STATUS_INACTIVE},
            )
    except Exception:
        logger.exception("pause_schedule unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_PAUSED)


def resume_schedule(user, schedule: Schedule) -> OperationResult:
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if schedule.status != Schedule.STATUS_INACTIVE:
        return OperationResult.failure("validation_form", MSG_FORBIDDEN)
    if not definition_ready_for_active(schedule):
        return OperationResult.failure("schedule_incomplete", MSG_RESUME_BLOCKED)
    try:
        with transaction.atomic():
            schedule.status = Schedule.STATUS_ACTIVE
            schedule.save(update_fields=["status", "updated_at"])
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_RESUMED,
                user,
                {"from": Schedule.STATUS_INACTIVE, "to": Schedule.STATUS_ACTIVE},
            )
    except Exception:
        logger.exception("resume_schedule unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=err.MSG_RESUMED)


def archive_schedule(user, schedule: Schedule) -> OperationResult:
    if not user_can_archive(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("validation_form", MSG_ARCHIVE_BLOCKED)
    if schedule.status not in {
        Schedule.STATUS_IN_PROGRESS,
        Schedule.STATUS_ACTIVE,
        Schedule.STATUS_INACTIVE,
    }:
        return OperationResult.failure("validation_form", MSG_ARCHIVE_BLOCKED)
    try:
        with transaction.atomic():
            previous = schedule.status
            schedule.status = Schedule.STATUS_ARCHIVED
            schedule.save(update_fields=["status", "updated_at"])
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_ARCHIVED,
                user,
                {"from": previous, "to": Schedule.STATUS_ARCHIVED},
            )
    except Exception:
        logger.exception("archive_schedule unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_ARCHIVED)


def _stepper_classes(done_flags: list[bool]) -> list[str]:
    """File Gate: hecho = is-done, primer pendiente = is-active, el resto = is-pending."""
    classes = []
    next_assigned = False
    for done in done_flags:
        if done:
            classes.append("is-done")
        elif not next_assigned:
            classes.append("is-active")
            next_assigned = True
        else:
            classes.append("is-pending")
    return classes


def get_hub_context(user, schedule: Schedule) -> dict:
    membership = get_membership(user, schedule)
    role_code, role_label = _role_for_row(user, schedule)
    member_count = ScheduleMembership.objects.filter(
        schedule=schedule,
        is_active=True,
    ).count()
    can_edit = user_can_edit(user, schedule)
    archived = schedule.status == Schedule.STATUS_ARCHIVED
    if schedule.status == Schedule.STATUS_IN_PROGRESS:
        if definition_ready_for_active(schedule):
            modules_note = (
                "Destino y disparador listos. PA o ED puede marcar el plan como Activo. "
                "No hay Ejecutar ahora."
            )
        elif schedule.target_complete:
            modules_note = (
                "Destino listo. Complete programación (M2) o dependencia (M6) para activar."
            )
        elif schedule.programming_complete or schedule.dependency_complete:
            modules_note = (
                "Disparador listo. Complete destino (M3) para poder activar."
            )
        else:
            modules_note = (
                "En proceso: complete destino (M3) y programación (M2) o dependencia (M6) "
                "para activar. No hay Ejecutar ahora."
            )
    elif schedule.status == Schedule.STATUS_ACTIVE:
        modules_note = "Plan activo. Pausar lo deja Inactivo; no aborta un Job ya encolado."
    elif schedule.status == Schedule.STATUS_INACTIVE:
        modules_note = (
            "Inactivo (pausado). Reanudar exige destino (M3) y programación (M2) o dependencia (M6)."
        )
    else:
        modules_note = "Archivado: baja lógica. El código no se reutiliza. Solo consulta."

    cron_done = schedule.programming_complete
    target_done = schedule.target_complete
    overlap_done = schedule.overlap_configured
    dependency_done = schedule.dependency_complete
    notify_done = schedule.notify_saved_at is not None
    activity_done = ScheduleTick.objects.filter(schedule=schedule).exists()
    audit_done = activity_done
    members_done = member_count > 1
    (
        cron_step_class,
        target_step_class,
        overlap_step_class,
        dependency_step_class,
        notify_step_class,
        activity_step_class,
        audit_step_class,
        members_step_class,
    ) = _stepper_classes(
        [
            cron_done,
            target_done,
            overlap_done,
            dependency_done,
            notify_done,
            activity_done,
            audit_done,
            members_done,
        ]
    )

    return {
        "visibility": schedule.visibility,
        "visibility_label": VISIBILITY_LABELS.get(
            schedule.visibility, schedule.visibility
        ),
        "status": schedule.status,
        "status_label": STATUS_LABELS.get(schedule.status, schedule.status),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == ScheduleMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": user_can_manage_members(user, schedule) and not archived,
        "can_edit": can_edit and not archived,
        "can_pause": can_edit and schedule.status == Schedule.STATUS_ACTIVE,
        "can_resume": can_edit and schedule.status == Schedule.STATUS_INACTIVE,
        "can_activate": can_edit
        and schedule.status == Schedule.STATUS_IN_PROGRESS
        and definition_ready_for_active(schedule),
        "can_archive": user_can_archive(user, schedule) and not archived,
        "membership": membership,
        "modules_pending_note": modules_note,
        "next_tick_label": cron_svc.first_tick_label(schedule),
        "last_tick_label": tick_svc.last_tick_label(schedule),
        "can_create": user_can_create(user),
        "programming_complete": schedule.programming_complete,
        "target_complete": schedule.target_complete,
        "overlap_configured": schedule.overlap_configured,
        "dependency_complete": schedule.dependency_complete,
        "notify_complete": notify_done,
        "activity_complete": activity_done,
        "audit_complete": audit_done,
        "members_complete": members_done,
        "cron_step_class": cron_step_class,
        "target_step_class": target_step_class,
        "overlap_step_class": overlap_step_class,
        "dependency_step_class": dependency_step_class,
        "notify_step_class": notify_step_class,
        "activity_step_class": activity_step_class,
        "audit_step_class": audit_step_class,
        "members_step_class": members_step_class,
    }


def list_audit_events(schedule: Schedule):
    return (
        ScheduleAuditEvent.objects.filter(schedule=schedule)
        .select_related("actor")
        .order_by("-created_at")
    )


def search_invitable(user, schedule: Schedule, q: str) -> list[dict]:
    term = (q or "").strip()
    if len(term) < SEARCH_MIN:
        return []
    member_ids = ScheduleMembership.objects.filter(
        schedule=schedule,
        is_active=True,
    ).values_list("user_id", flat=True)
    qs = (
        UserProfile.objects.filter(
            company=schedule.company,
            user_type=UserProfile.USER_FINAL,
            status=UserProfile.STATUS_ACTIVE,
        )
        .exclude(user_id__in=member_ids)
        .exclude(user_id=user.id)
        .select_related("user")
        .filter(
            Q(user__username__icontains=term)
            | Q(user__email__icontains=term)
            | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
        )
        .order_by("user__username")[:SEARCH_LIMIT]
    )
    rows = []
    for profile in qs:
        full = profile.user.get_full_name() or "—"
        rows.append(
            {
                "id": str(profile.user_id),
                "label": f"{profile.user.username} — {full}",
                "username": profile.user.username,
            }
        )
    return rows


def list_members(schedule: Schedule):
    return (
        ScheduleMembership.objects.filter(schedule=schedule)
        .select_related("user", "invited_by")
        .order_by("created_at")
    )


def invite_member(actor, schedule: Schedule, data: dict) -> OperationResult:
    if not user_can_manage_members(actor, schedule):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)

    user_id = data.get("user_id", "").strip()
    role = resolve_role_code(data.get("role", "").strip()) or ""
    if role not in ScheduleMembership.SCHEDULE_ROLES:
        role = ""

    errors: dict[str, list[str]] = {}
    if not user_id:
        errors.setdefault("user", []).append("Busque y elija un usuario UF.")
    if not role:
        errors.setdefault("role", []).append("Seleccione un rol válido.")
    if errors:
        return OperationResult.failure("validation_form", "Revise los datos del formulario.", errors=errors)

    try:
        profile = UserProfile.objects.select_related("user").get(
            user_id=user_id,
            company=schedule.company,
            user_type=UserProfile.USER_FINAL,
        )
    except (UserProfile.DoesNotExist, ValueError):
        return OperationResult.failure(
            "invalid_user",
            "El usuario seleccionado no es válido para este plan.",
            errors={"user": ["Usuario no disponible en su compañía."]},
        )

    if ScheduleMembership.objects.filter(
        schedule=schedule,
        user=profile.user,
        is_active=True,
    ).exists():
        return OperationResult.failure(
            "duplicate",
            "El usuario ya es miembro activo del plan.",
            errors={"user": ["Ya tiene membresía activa."]},
        )

    try:
        membership, created = ScheduleMembership.objects.get_or_create(
            schedule=schedule,
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
        logger.exception(
            "invite_schedule_member unexpected schedule=%s user=%s",
            schedule.pk,
            user_id,
        )
        return OperationResult.failure("unexpected", "Ocurrió un error al autorizar el miembro.")

    return OperationResult.success(
        user_message=f"Miembro «{profile.user.username}» autorizado correctamente.",
    )


def update_member_role(actor, schedule, membership_id: str, role_raw: str) -> OperationResult:
    if not user_can_manage_members(actor, schedule):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)
    role = resolve_role_code(role_raw) or ""
    if role not in ScheduleMembership.SCHEDULE_ROLES:
        return OperationResult.failure("validation_form", "Seleccione un rol válido.")
    try:
        membership = ScheduleMembership.objects.select_related("user").get(
            pk=membership_id,
            schedule=schedule,
        )
    except (ScheduleMembership.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "No se encontró la membresía.")
    if membership.user_id == schedule.owner_id:
        return OperationResult.failure("forbidden", "El owner no se revoca ni cambia de rol.")
    membership.role = role
    membership.save(update_fields=["role"])
    return OperationResult.success(
        user_message=f"Rol de «{membership.user.username}» actualizado.",
    )


def set_member_active(actor, schedule, membership_id: str, *, active: bool) -> OperationResult:
    if not user_can_manage_members(actor, schedule):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)
    try:
        membership = ScheduleMembership.objects.select_related("user").get(
            pk=membership_id,
            schedule=schedule,
        )
    except (ScheduleMembership.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "No se encontró la membresía.")
    if membership.user_id == schedule.owner_id:
        return OperationResult.failure("forbidden", "El owner no se revoca ni cambia de rol.")
    membership.is_active = active
    membership.save(update_fields=["is_active"])
    verb = "reactivado" if active else "revocado"
    return OperationResult.success(
        user_message=f"Acceso de «{membership.user.username}» {verb}.",
    )


def programming_posted_from_request(post) -> dict:
    return {
        "schedule_kind": (post.get("schedule_kind") or "").strip(),
        "time_local": (post.get("time_local") or "").strip(),
        "day_of_week": (post.get("day_of_week") or "").strip(),
        "monthly_mode": (post.get("monthly_mode") or "").strip(),
        "day_of_month": (post.get("day_of_month") or "").strip(),
        "cron_expr": (post.get("cron_expr") or "").strip(),
        "timezone": (post.get("timezone") or "").strip(),
    }


def save_programming(user, schedule: Schedule, data: dict) -> OperationResult:
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_CRON_FORBIDDEN)

    kind = data.get("schedule_kind")
    errors: dict[str, list[str]] = {}
    if kind not in cron_svc.VALID_KINDS:
        errors.setdefault("schedule_kind", []).append("Seleccione una frecuencia.")

    tzinfo, tz_name = cron_svc.resolve_timezone(data.get("timezone") or "")
    if tzinfo is None:
        errors.setdefault("timezone", []).append(MSG_TIMEZONE_INVALID)

    day_of_week = None
    day_of_month = None
    monthly_mode = ""
    time_local = ""
    cron_expr = ""

    if kind == cron_svc.KIND_CRON:
        ok, msg = cron_svc.validate_cron_expr(data.get("cron_expr") or "")
        if not ok:
            errors.setdefault("cron_expr", []).append(msg)
        else:
            cron_expr = (data.get("cron_expr") or "").strip()
    elif kind in cron_svc.VALID_KINDS:
        parsed = cron_svc.parse_time_local(data.get("time_local") or "")
        if parsed is None:
            errors.setdefault("time_local", []).append("Indique la hora local (HH:MM).")
        else:
            time_local = (data.get("time_local") or "").strip()
        if kind == cron_svc.KIND_WEEKLY:
            try:
                day_of_week = int(data.get("day_of_week"))
            except (TypeError, ValueError):
                day_of_week = -1
            if day_of_week not in range(0, 7):
                errors.setdefault("day_of_week", []).append("Seleccione el día de la semana.")
        if kind == cron_svc.KIND_MONTHLY:
            monthly_mode = data.get("monthly_mode") or cron_svc.MONTHLY_LAST
            if monthly_mode not in {cron_svc.MONTHLY_LAST, cron_svc.MONTHLY_SPECIFIC}:
                errors.setdefault("monthly_mode", []).append("Seleccione el modo mensual.")
            elif monthly_mode == cron_svc.MONTHLY_SPECIFIC:
                try:
                    day_of_month = int(data.get("day_of_month"))
                except (TypeError, ValueError):
                    day_of_month = 0
                if day_of_month < 1 or day_of_month > 31:
                    errors.setdefault("day_of_month", []).append(
                        "Indique un día entre 1 y 31."
                    )

    if errors:
        if list(errors.keys()) == ["timezone"]:
            return OperationResult.failure(
                err.TIMEZONE_INVALID, MSG_TIMEZONE_INVALID, errors=errors
            )
        if kind == cron_svc.KIND_CRON and "cron_expr" in errors:
            return OperationResult.failure(
                err.CRON_INVALID, err.MSG_CRON_INVALID, errors=errors
            )
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    if kind != cron_svc.KIND_CRON:
        cron_expr = cron_svc.materialize_cron_expr(
            {
                "schedule_kind": kind,
                "time_local": time_local,
                "day_of_week": day_of_week,
                "monthly_mode": monthly_mode,
                "day_of_month": day_of_month,
            }
        )

    previous_status = schedule.status
    try:
        with transaction.atomic():
            schedule.schedule_kind = kind
            schedule.time_local = time_local
            schedule.day_of_week = day_of_week
            schedule.monthly_mode = monthly_mode
            schedule.day_of_month = day_of_month
            schedule.cron_expr = cron_expr
            schedule.timezone = tz_name
            schedule.programming_saved_at = timezone.now()
            schedule.save(
                update_fields=[
                    "schedule_kind",
                    "time_local",
                    "day_of_week",
                    "monthly_mode",
                    "day_of_month",
                    "cron_expr",
                    "timezone",
                    "programming_saved_at",
                    "updated_at",
                ]
            )
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {
                    "schedule_kind": kind,
                    "cron_expr": cron_expr,
                    "timezone": tz_name,
                    "time_local": time_local,
                    "status_unchanged": previous_status,
                },
            )
    except Exception:
        logger.exception("save_programming unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(
        user_message=MSG_CRON_SAVED,
        payload={"schedule": schedule},
    )


def activate_schedule(user, schedule: Schedule) -> OperationResult:
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if schedule.status != Schedule.STATUS_IN_PROGRESS:
        return OperationResult.failure("validation_form", MSG_FORBIDDEN)
    if not definition_ready_for_active(schedule):
        return OperationResult.failure("schedule_incomplete", MSG_RESUME_BLOCKED)
    try:
        with transaction.atomic():
            schedule.status = Schedule.STATUS_ACTIVE
            schedule.save(update_fields=["status", "updated_at"])
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {"status": Schedule.STATUS_ACTIVE, "action": "activate"},
            )
    except Exception:
        logger.exception("activate_schedule unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_ACTIVATED)


def save_target(user, schedule: Schedule, data: dict) -> OperationResult:
    from apps.file_pipeline.models import PipelineDefinition
    from apps.projects.models import Project

    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", target_svc.MSG_FORBIDDEN_SAVE)

    mode = data.get("target_mode")
    origin = data.get("input_origin")
    errors: dict[str, list[str]] = {}
    project = None
    pipeline = None
    version_number = None
    kind = ""
    watch_id = ""
    artifact_ref = ""
    resolved = False

    if mode not in {target_svc.MODE_JOB, target_svc.MODE_PIPELINE}:
        errors.setdefault("target_mode", []).append("Seleccione Job de app o Pipeline.")
    if origin not in {
        target_svc.ORIGIN_WATCH,
        target_svc.ORIGIN_ARTIFACT,
        target_svc.ORIGIN_NONE,
    }:
        errors.setdefault("input_origin", []).append("Seleccione el origen de entrada.")

    if mode == target_svc.MODE_JOB and not errors.get("target_mode"):
        kind = data.get("kind") or ""
        if kind not in target_svc.FILE_JOB_KINDS:
            errors.setdefault("kind", []).append("Seleccione una app válida.")
        pid = data.get("project_id") or ""
        if not pid:
            errors.setdefault("project_id", []).append(target_svc.MSG_NEED_PROJECT)
        else:
            try:
                project = Project.objects.select_related(
                    "dms_config", "dms_config__current_version", "company"
                ).get(pk=pid)
            except (Project.DoesNotExist, ValueError):
                errors.setdefault("project_id", []).append(target_svc.MSG_NEED_PROJECT)
            else:
                if project.company_id != schedule.company_id:
                    return OperationResult.failure(
                        "schedule_target_cross_tenant", MSG_NO_ACCESS
                    )
                spec = target_svc.kind_spec(kind)
                if spec and project.project_kind != spec["project_kind"]:
                    errors.setdefault("project_id", []).append(
                        "El proyecto no corresponde a la app elegida."
                    )
                version_number = target_svc.published_version_number(project)
                if version_number is None:
                    return OperationResult.failure(
                        "schedule_no_published_target",
                        target_svc.MSG_NO_PUBLISHED,
                        errors={"project_id": [target_svc.MSG_NO_PUBLISHED]},
                    )
                if not target_svc.actor_can_run_target(user, project=project):
                    return OperationResult.failure(
                        "schedule_forbidden",
                        target_svc.MSG_FORBIDDEN_RUN,
                    )
        if origin == target_svc.ORIGIN_NONE:
            return OperationResult.failure(
                "schedule_missing_input",
                target_svc.MSG_MISSING_JOB_NONE,
                errors={"input_origin": [target_svc.MSG_MISSING_JOB_NONE]},
            )

    if mode == target_svc.MODE_PIPELINE and not errors.get("target_mode"):
        plid = data.get("pipeline_id") or ""
        if not plid:
            errors.setdefault("pipeline_id", []).append(target_svc.MSG_NEED_PIPELINE)
        else:
            try:
                pipeline = PipelineDefinition.objects.select_related(
                    "current_version", "company"
                ).get(pk=plid)
            except (PipelineDefinition.DoesNotExist, ValueError):
                errors.setdefault("pipeline_id", []).append(target_svc.MSG_NEED_PIPELINE)
            else:
                if pipeline.company_id != schedule.company_id:
                    return OperationResult.failure(
                        "schedule_target_cross_tenant", MSG_NO_ACCESS
                    )
                if (
                    pipeline.current_version_id is None
                    or pipeline.status != PipelineDefinition.STATUS_ACTIVE
                ):
                    return OperationResult.failure(
                        "schedule_no_published_target",
                        target_svc.MSG_NO_PUBLISHED,
                        errors={"pipeline_id": [target_svc.MSG_NO_PUBLISHED]},
                    )
                version_number = pipeline.current_version.version_number
                if not target_svc.actor_can_run_target(user, pipeline=pipeline):
                    return OperationResult.failure(
                        "schedule_forbidden",
                        target_svc.MSG_FORBIDDEN_RUN,
                    )
        if origin == target_svc.ORIGIN_NONE:
            resolved = (data.get("pipeline_inputs_resolved") or "") in {"1", "on", "true"}
            if not resolved:
                return OperationResult.failure(
                    "schedule_missing_input",
                    target_svc.MSG_MISSING_NONE_CONFIRM,
                    errors={"pipeline_inputs_resolved": [target_svc.MSG_MISSING_NONE_CONFIRM]},
                )

    if origin == target_svc.ORIGIN_WATCH:
        watch_id = (data.get("watch_id") or "").strip()
        if not watch_id:
            errors.setdefault("watch_id", []).append(target_svc.MSG_MISSING_WATCH)
    if origin == target_svc.ORIGIN_ARTIFACT:
        artifact_ref = (data.get("artifact_ref") or "").strip()
        if not artifact_ref:
            errors.setdefault("artifact_ref", []).append(target_svc.MSG_MISSING_ARTIFACT)
        elif len(artifact_ref) > 128:
            errors.setdefault("artifact_ref", []).append("Máximo 128 caracteres.")

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    previous_status = schedule.status
    try:
        with transaction.atomic():
            schedule.target_mode = mode
            schedule.target_kind = kind if mode == target_svc.MODE_JOB else ""
            schedule.target_project = project
            schedule.target_pipeline = pipeline
            schedule.published_version_number = version_number
            schedule.input_origin = origin
            schedule.watch_id = watch_id
            schedule.artifact_ref = artifact_ref
            schedule.pipeline_inputs_resolved = resolved
            schedule.target_saved_at = timezone.now()
            schedule.save(
                update_fields=[
                    "target_mode",
                    "target_kind",
                    "target_project",
                    "target_pipeline",
                    "published_version_number",
                    "input_origin",
                    "watch_id",
                    "artifact_ref",
                    "pipeline_inputs_resolved",
                    "target_saved_at",
                    "updated_at",
                ]
            )
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {
                    "target_mode": mode,
                    "kind": kind,
                    "project_id": str(project.id) if project else "",
                    "pipeline_id": str(pipeline.id) if pipeline else "",
                    "input_origin": origin,
                    "watch_id": watch_id,
                    "artifact_ref": artifact_ref[:16] if artifact_ref else "",
                    "status_unchanged": previous_status,
                },
            )
    except Exception:
        logger.exception("save_target unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(
        user_message=MSG_TARGET_SAVED,
        payload={"schedule": schedule},
    )


VALID_OVERLAP = {
    Schedule.OVERLAP_SKIP,
    Schedule.OVERLAP_QUEUE,
    Schedule.OVERLAP_CANCEL,
}


def overlap_posted_from_request(post) -> dict:
    return {"overlap_policy": (post.get("overlap_policy") or "").strip()}


def save_overlap(user, schedule: Schedule, data: dict) -> OperationResult:
    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", MSG_OVERLAP_FORBIDDEN)
    policy = data.get("overlap_policy") or ""
    if policy not in VALID_OVERLAP:
        return OperationResult.failure(
            "validation_form",
            MSG_VALIDATION,
            errors={"overlap_policy": [MSG_OVERLAP_INVALID]},
        )
    previous_status = schedule.status
    previous_policy = schedule.overlap_policy
    try:
        with transaction.atomic():
            schedule.overlap_policy = policy
            schedule.overlap_saved_at = timezone.now()
            schedule.save(
                update_fields=["overlap_policy", "overlap_saved_at", "updated_at"]
            )
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {
                    "overlap_policy": policy,
                    "overlap_policy_from": previous_policy,
                    "status_unchanged": previous_status,
                },
            )
    except Exception:
        logger.exception("save_overlap unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(
        user_message=MSG_OVERLAP_SAVED,
        payload={"schedule": schedule},
    )


def save_dependency(user, schedule: Schedule, data: dict) -> OperationResult:
    from apps.file_pipeline.models import PipelineDefinition
    from apps.projects.models import Project

    if schedule.status == Schedule.STATUS_ARCHIVED:
        return OperationResult.failure("schedule_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, schedule):
        return OperationResult.failure("schedule_forbidden", dep_svc.MSG_FORBIDDEN)

    mode = data.get("trigger_mode") or Schedule.TRIGGER_TIME
    errors: dict[str, list[str]] = {}
    parent_kind = ""
    on_parent = ""
    parent_project = None
    parent_pipeline = None

    if mode not in {Schedule.TRIGGER_TIME, Schedule.TRIGGER_DEPENDENCY}:
        errors.setdefault("trigger_mode", []).append("Seleccione reloj o dependencia.")

    if mode == Schedule.TRIGGER_DEPENDENCY:
        parent_kind = data.get("parent_kind") or ""
        if parent_kind not in {Schedule.PARENT_JOB, Schedule.PARENT_PIPELINE}:
            errors.setdefault("parent_kind", []).append(dep_svc.MSG_NEED_PARENT)
        on_parent = data.get("on_parent") or Schedule.ON_SUCCEEDED
        if on_parent not in dep_svc.ON_OK:
            errors.setdefault("on_parent", []).append("Seleccione la condición del padre.")
        if parent_kind == Schedule.PARENT_JOB:
            pid = data.get("parent_project_id") or ""
            if not pid:
                errors.setdefault("parent_project_id", []).append(dep_svc.MSG_NEED_PARENT)
            else:
                try:
                    parent_project = Project.objects.select_related("company").get(pk=pid)
                except (Project.DoesNotExist, ValueError):
                    errors.setdefault("parent_project_id", []).append(dep_svc.MSG_NEED_PARENT)
                else:
                    if parent_project.company_id != schedule.company_id:
                        return OperationResult.failure(
                            "schedule_dependency_cross_tenant", MSG_NO_ACCESS
                        )
                    if on_parent == Schedule.ON_ACCEPTED and parent_project.project_kind != Project.KIND_FILE_GATE:
                        return OperationResult.failure(
                            "validation_form",
                            dep_svc.MSG_ACCEPTED_NOT_GATE,
                            errors={"on_parent": [dep_svc.MSG_ACCEPTED_NOT_GATE]},
                        )
                    if (
                        schedule.target_mode == Schedule.TARGET_JOB
                        and schedule.target_project_id
                        and str(schedule.target_project_id) == str(parent_project.id)
                    ):
                        return OperationResult.failure(
                            "schedule_dependency_cycle",
                            dep_svc.MSG_CYCLE,
                            errors={"parent_project_id": [dep_svc.MSG_CYCLE]},
                        )
        if parent_kind == Schedule.PARENT_PIPELINE:
            if on_parent == Schedule.ON_ACCEPTED:
                return OperationResult.failure(
                    "validation_form",
                    dep_svc.MSG_ACCEPTED_NOT_GATE,
                    errors={"on_parent": [dep_svc.MSG_ACCEPTED_NOT_GATE]},
                )
            plid = data.get("parent_pipeline_id") or ""
            if not plid:
                errors.setdefault("parent_pipeline_id", []).append(dep_svc.MSG_NEED_PARENT)
            else:
                try:
                    parent_pipeline = PipelineDefinition.objects.select_related(
                        "company", "current_version"
                    ).get(pk=plid)
                except (PipelineDefinition.DoesNotExist, ValueError):
                    errors.setdefault("parent_pipeline_id", []).append(dep_svc.MSG_NEED_PARENT)
                else:
                    if parent_pipeline.company_id != schedule.company_id:
                        return OperationResult.failure(
                            "schedule_dependency_cross_tenant", MSG_NO_ACCESS
                        )
                    if (
                        parent_pipeline.current_version_id is None
                        or parent_pipeline.status != PipelineDefinition.STATUS_ACTIVE
                    ):
                        return OperationResult.failure(
                            "schedule_no_published_target",
                            target_svc.MSG_NO_PUBLISHED,
                            errors={"parent_pipeline_id": [target_svc.MSG_NO_PUBLISHED]},
                        )
                    if (
                        schedule.target_mode == Schedule.TARGET_PIPELINE
                        and schedule.target_pipeline_id
                        and str(schedule.target_pipeline_id) == str(parent_pipeline.id)
                    ):
                        return OperationResult.failure(
                            "schedule_dependency_cycle",
                            dep_svc.MSG_CYCLE,
                            errors={"parent_pipeline_id": [dep_svc.MSG_CYCLE]},
                        )

    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    previous_status = schedule.status
    try:
        with transaction.atomic():
            schedule.trigger_mode = mode
            if mode == Schedule.TRIGGER_TIME:
                schedule.parent_kind = ""
                schedule.parent_project = None
                schedule.parent_pipeline = None
                schedule.on_parent = ""
                schedule.dependency_saved_at = timezone.now()
            else:
                schedule.parent_kind = parent_kind
                schedule.parent_project = parent_project
                schedule.parent_pipeline = parent_pipeline
                schedule.on_parent = on_parent
                schedule.dependency_saved_at = timezone.now()
            schedule.save(
                update_fields=[
                    "trigger_mode",
                    "parent_kind",
                    "parent_project",
                    "parent_pipeline",
                    "on_parent",
                    "dependency_saved_at",
                    "updated_at",
                ]
            )
            _record_event(
                schedule,
                ScheduleAuditEvent.EVENT_UPDATED,
                user,
                {
                    "trigger_mode": mode,
                    "parent_kind": parent_kind,
                    "on_parent": on_parent,
                    "status_unchanged": previous_status,
                },
            )
    except Exception:
        logger.exception("save_dependency unexpected id=%s", schedule.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(
        user_message=MSG_DEPENDENCY_SAVED,
        payload={"schedule": schedule},
    )
