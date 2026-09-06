"""M1 File Watch: ciclo de vida de la bandeja (listado, alta, hub, miembros, auditoría CRUD)."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.dms.catalogs.services.permission_package_service import resolve_role_code
from apps.file_pipeline.models import PipelineDefinition
from apps.file_scheduler.models import Schedule
from apps.file_watch.models import Watch, WatchAuditEvent, WatchBatch, WatchMembership
from apps.file_watch.services import watch_audit as audit_svc
from apps.file_watch.services import watch_errors as err
from apps.projects.services.project_service import SLUG_RE, find_project_by_slug, slug_duplicate_message

logger = logging.getLogger(__name__)

VISIBILITY_LABELS = {
    Watch.VISIBILITY_COMPANY: "Público",
    Watch.VISIBILITY_MEMBERS_ONLY: "Privado",
}

STATUS_LABELS = {
    Watch.STATUS_ACTIVE: "Activo",
    Watch.STATUS_IN_PROGRESS: "En proceso",
    Watch.STATUS_INACTIVE: "Inactivo",
    Watch.STATUS_ARCHIVED: "Archivado",
}

SOURCE_KIND_LABELS = {
    Watch.SOURCE_SFTP: "SFTP",
    Watch.SOURCE_MANAGED_FOLDER: "Carpeta",
    Watch.SOURCE_API_PUSH: "API push",
}

ROLE_LABELS = {
    WatchMembership.ROLE_PA: "PA — Admin",
    WatchMembership.ROLE_ED: "ED — Editor",
    WatchMembership.ROLE_GE: "GE — Ejecutor",
    WatchMembership.ROLE_CO: "CO — Consulta",
    "company_viewer": "CO — Consulta (compañía)",
}

DEFAULT_DESCRIPTION = (
    "Bandeja de File Watch: detecta llegadas de archivo y deja lotes o dispara un Job."
)

MSG_NO_ACCESS = "No tiene acceso a esta bandeja."
MSG_CREATE_FORBIDDEN = (
    "Solo usuarios US con rol PA o ED de esta compañía pueden crear bandejas."
)
MSG_CREATED = err.MSG_CREATED
MSG_UPDATED = err.MSG_UPDATED
MSG_PAUSED = err.MSG_PAUSED_OK
MSG_ARCHIVED = err.MSG_ARCHIVED
MSG_PA_ONLY = "Solo el administrador de la bandeja (PA) puede gestionar miembros."
MSG_FORBIDDEN = err.MSG_FORBIDDEN
MSG_RESUME_BLOCKED = err.MSG_INCOMPLETE
MSG_PAUSE_BLOCKED = "Solo se puede pausar una bandeja Activa."
MSG_ARCHIVE_BLOCKED = "No se puede archivar esta bandeja."
MSG_COMPANY_INACTIVE = "La compañía no está activa."
MSG_MODULE_PENDING = "Este módulo se implementará en una fase posterior."
MSG_VALIDATION = "Revise los datos marcados; no se pudo guardar."
MSG_UNEXPECTED = "Ocurrió un error al guardar. Si persiste, contacte al administrador."
MSG_SLUG_TAKEN = err.MSG_SLUG_TAKEN
MSG_ACTIVATED = err.MSG_ACTIVATED

SEARCH_LIMIT = 20
SEARCH_MIN = 2

PENDING_MODULES = {
    "source": "Origen",
    "intake": "Intake",
    "route": "Enrutado",
    "fire": "Disparo",
    "idempotency": "Idempotencia",
    "notify": "Avisos",
    "batches": "Llegadas / lotes",
    "audit": "Auditoría",
}


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


def get_membership(user, watch: Watch) -> WatchMembership | None:
    return (
        WatchMembership.objects.filter(
            watch=watch,
            user=user,
            is_active=True,
        )
        .select_related("user")
        .first()
    )


def user_can_view(user, watch: Watch) -> bool:
    if not getattr(user, "profile", None):
        return False
    if watch.company_id != user.profile.company_id:
        return False
    if not watch.company.is_active:
        return False
    if get_membership(user, watch) is not None:
        return True
    return watch.visibility == Watch.VISIBILITY_COMPANY


def user_can_edit(user, watch: Watch) -> bool:
    if watch.status == Watch.STATUS_ARCHIVED:
        return False
    membership = get_membership(user, watch)
    return membership is not None and membership.role in {
        WatchMembership.ROLE_PA,
        WatchMembership.ROLE_ED,
    }


def user_can_archive(user, watch: Watch) -> bool:
    if watch.status == Watch.STATUS_ARCHIVED:
        return False
    membership = get_membership(user, watch)
    return membership is not None and membership.role == WatchMembership.ROLE_PA


def user_can_manage_members(user, watch: Watch) -> bool:
    return user_can_archive(user, watch)


def get_watch_for_user(user, slug: str) -> Watch | None:
    try:
        watch = Watch.objects.select_related("company", "owner").get(
            company=user.profile.company,
            slug=slug,
        )
    except Watch.DoesNotExist:
        return None
    if not user_can_view(user, watch):
        return None
    return watch


def visible_qs(user):
    company = user.profile.company
    if not company.is_active:
        return Watch.objects.none()
    member_ids = WatchMembership.objects.filter(
        user=user,
        is_active=True,
        watch__company=company,
    ).values_list("watch_id", flat=True)
    return (
        Watch.objects.filter(company=company)
        .filter(
            Q(id__in=member_ids)
            | Q(visibility=Watch.VISIBILITY_COMPANY)
        )
        .select_related("owner", "company")
        .distinct()
    )


def _role_for_row(user, watch: Watch) -> tuple[str | None, str]:
    membership = get_membership(user, watch)
    if membership is not None:
        return membership.role, ROLE_LABELS.get(membership.role, membership.role)
    return None, ROLE_LABELS["company_viewer"]


def _source_label(watch: Watch) -> str:
    if not watch.source_kind:
        return "Sin origen (M2)"
    return SOURCE_KIND_LABELS.get(watch.source_kind, watch.source_kind)


def _last_arrival_label(watch: Watch) -> str:
    batch = (
        WatchBatch.objects.filter(watch=watch)
        .exclude(ingested_at__isnull=True)
        .order_by("-ingested_at")
        .first()
    )
    if batch is None or batch.ingested_at is None:
        return "—"
    return batch.ingested_at.strftime("%d/%m %H:%M")


def list_watches(user):
    qs = visible_qs(user).order_by("-updated_at")
    rows = []
    for watch in qs:
        role_code, role_label = _role_for_row(user, watch)
        archived = watch.status == Watch.STATUS_ARCHIVED
        rows.append(
            {
                "watch": watch,
                "role": role_code,
                "role_label": role_label,
                "visibility": watch.visibility,
                "visibility_label": VISIBILITY_LABELS.get(
                    watch.visibility, watch.visibility
                ),
                "status": watch.status,
                "status_label": STATUS_LABELS.get(watch.status, watch.status),
                "source_label": _source_label(watch),
                "last_arrival_label": _last_arrival_label(watch),
                "can_edit": user_can_edit(user, watch) and not archived,
                "can_manage_members": user_can_manage_members(user, watch)
                and not archived,
                "can_archive": user_can_archive(user, watch) and not archived,
                "can_pause": user_can_edit(user, watch)
                and watch.status == Watch.STATUS_ACTIVE,
                "can_resume": user_can_edit(user, watch)
                and watch.status == Watch.STATUS_INACTIVE,
            }
        )
    operative = [r for r in rows if r["status"] != Watch.STATUS_ARCHIVED]
    stats = {
        "total": len(operative),
        "active": sum(1 for r in operative if r["status"] == Watch.STATUS_ACTIVE),
        "in_progress": sum(
            1 for r in operative if r["status"] == Watch.STATUS_IN_PROGRESS
        ),
        "inactive": sum(
            1 for r in operative if r["status"] == Watch.STATUS_INACTIVE
        ),
    }
    return rows, stats


def default_posted() -> dict:
    return {
        "name": "",
        "slug": "",
        "description": "",
        "visibility": Watch.VISIBILITY_MEMBERS_ONLY,
    }


def posted_from_request(post) -> dict:
    return {
        "name": post.get("name", "").strip(),
        "slug": post.get("slug", "").strip().lower(),
        "description": post.get("description", "").strip(),
        "visibility": post.get("visibility", "").strip(),
    }


def validate_identity(data: dict, company, *, watch: Watch | None = None) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    name = data.get("name", "").strip()
    if not name:
        errors.setdefault("name", []).append("Ingrese el nombre de la bandeja.")
    elif len(name) > 200:
        errors.setdefault("name", []).append("Máximo 200 caracteres.")

    if watch is None:
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
                errors.setdefault("slug", []).append(
                    "Ya existe un plan de File Scheduler con este código."
                )
            elif Watch.objects.filter(company=company, slug=slug).exists():
                errors.setdefault("slug", []).append(MSG_SLUG_TAKEN)

    description = data.get("description", "")
    if len(description) > 5000:
        errors.setdefault("description", []).append("La descripción es demasiado larga.")

    visibility = data.get("visibility", "")
    valid_vis = {c[0] for c in Watch.VISIBILITY_CHOICES}
    if visibility not in valid_vis:
        errors.setdefault("visibility", []).append("Seleccione una visibilidad válida.")
    return errors


def create_watch(user, data: dict) -> OperationResult:
    if not user_can_create(user):
        return OperationResult.failure("watch_forbidden", MSG_CREATE_FORBIDDEN)

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
            watch = Watch.objects.create(
                company=company,
                name=data["name"],
                slug=data["slug"],
                description=description,
                owner=user,
                visibility=data["visibility"],
                status=Watch.STATUS_IN_PROGRESS,
            )
            WatchMembership.objects.create(
                watch=watch,
                user=user,
                role=WatchMembership.ROLE_PA,
                invited_by=None,
                is_active=True,
            )
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_CREATED,
                user,
                {
                    "slug": watch.slug,
                    "name": watch.name,
                    "visibility": watch.visibility,
                    "status": watch.status,
                },
            )
    except IntegrityError:
        logger.exception("create_watch IntegrityError slug=%s", data.get("slug"))
        return OperationResult.failure(
            "watch_slug_taken",
            MSG_SLUG_TAKEN,
            errors={"slug": [MSG_SLUG_TAKEN]},
        )
    except Exception:
        logger.exception("create_watch unexpected")
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(
        user_message=MSG_CREATED,
        payload={"watch": watch},
    )


def update_watch(user, watch: Watch, data: dict) -> OperationResult:
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure("watch_forbidden", MSG_FORBIDDEN)
    if not user_can_edit(user, watch):
        return OperationResult.failure("watch_forbidden", MSG_FORBIDDEN)

    errors = validate_identity(data, watch.company, watch=watch)
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)

    description = data.get("description", "").strip()
    changed = {}
    if watch.name != data["name"]:
        changed["name"] = {"from": watch.name, "to": data["name"]}
        watch.name = data["name"]
    if watch.description != description:
        changed["description"] = True
        watch.description = description
    if watch.visibility != data["visibility"]:
        changed["visibility"] = {
            "from": watch.visibility,
            "to": data["visibility"],
        }
        watch.visibility = data["visibility"]

    if not changed:
        return OperationResult.success(user_message=MSG_UPDATED, payload={"watch": watch})

    try:
        with transaction.atomic():
            watch.save(update_fields=["name", "description", "visibility", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_UPDATED,
                user,
                {"fields": list(changed.keys()), "diff": changed},
            )
    except Exception:
        logger.exception("update_watch unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)

    return OperationResult.success(user_message=MSG_UPDATED, payload={"watch": watch})


def definition_ready_for_active(watch: Watch) -> bool:
    from apps.file_watch.services import watch_fire as fire_svc

    return fire_svc.activation_checks(watch) is None


def pause_watch(user, watch: Watch) -> OperationResult:
    if not user_can_edit(user, watch):
        return OperationResult.failure("watch_forbidden", MSG_FORBIDDEN)
    if watch.status != Watch.STATUS_ACTIVE:
        return OperationResult.failure("validation_form", MSG_PAUSE_BLOCKED)
    try:
        with transaction.atomic():
            watch.status = Watch.STATUS_INACTIVE
            watch.save(update_fields=["status", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_PAUSED,
                user,
                {"from": Watch.STATUS_ACTIVE, "to": Watch.STATUS_INACTIVE},
            )
    except Exception:
        logger.exception("pause_watch unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_PAUSED)


def resume_watch(user, watch: Watch) -> OperationResult:
    if not user_can_edit(user, watch):
        return OperationResult.failure("watch_forbidden", MSG_FORBIDDEN)
    if watch.status != Watch.STATUS_INACTIVE:
        return OperationResult.failure("validation_form", MSG_FORBIDDEN)
    if not definition_ready_for_active(watch):
        return OperationResult.failure("watch_incomplete", MSG_RESUME_BLOCKED)
    try:
        with transaction.atomic():
            watch.status = Watch.STATUS_ACTIVE
            watch.save(update_fields=["status", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_RESUMED,
                user,
                {"from": Watch.STATUS_INACTIVE, "to": Watch.STATUS_ACTIVE},
            )
    except Exception:
        logger.exception("resume_watch unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=err.MSG_RESUMED)


def activate_watch(user, watch: Watch) -> OperationResult:
    if not user_can_edit(user, watch):
        return OperationResult.failure("watch_forbidden", MSG_FORBIDDEN)
    if watch.status != Watch.STATUS_IN_PROGRESS:
        return OperationResult.failure("validation_form", MSG_FORBIDDEN)
    if not definition_ready_for_active(watch):
        return OperationResult.failure("watch_incomplete", MSG_RESUME_BLOCKED)
    try:
        with transaction.atomic():
            watch.status = Watch.STATUS_ACTIVE
            watch.save(update_fields=["status", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_UPDATED,
                user,
                {"status": Watch.STATUS_ACTIVE, "action": "activate"},
            )
    except Exception:
        logger.exception("activate_watch unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_ACTIVATED)


def archive_watch(user, watch: Watch) -> OperationResult:
    if not user_can_archive(user, watch):
        return OperationResult.failure("watch_forbidden", MSG_FORBIDDEN)
    if watch.status == Watch.STATUS_ARCHIVED:
        return OperationResult.failure("validation_form", MSG_ARCHIVE_BLOCKED)
    if watch.status not in {
        Watch.STATUS_IN_PROGRESS,
        Watch.STATUS_ACTIVE,
        Watch.STATUS_INACTIVE,
    }:
        return OperationResult.failure("validation_form", MSG_ARCHIVE_BLOCKED)
    try:
        with transaction.atomic():
            previous = watch.status
            watch.status = Watch.STATUS_ARCHIVED
            watch.save(update_fields=["status", "updated_at"])
            audit_svc.append_event(
                watch,
                WatchAuditEvent.EVENT_ARCHIVED,
                user,
                {"from": previous, "to": Watch.STATUS_ARCHIVED},
            )
    except Exception:
        logger.exception("archive_watch unexpected id=%s", watch.pk)
        return OperationResult.failure("unexpected", MSG_UNEXPECTED)
    return OperationResult.success(user_message=MSG_ARCHIVED)


def _stepper_classes(done_flags: list[bool]) -> list[str]:
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


def get_hub_context(user, watch: Watch) -> dict:
    membership = get_membership(user, watch)
    role_code, role_label = _role_for_row(user, watch)
    member_count = WatchMembership.objects.filter(
        watch=watch,
        is_active=True,
    ).count()
    can_edit = user_can_edit(user, watch)
    archived = watch.status == Watch.STATUS_ARCHIVED

    if watch.status == Watch.STATUS_IN_PROGRESS:
        if definition_ready_for_active(watch):
            modules_note = (
                "Origen y disparo listos. PA o ED puede marcar la bandeja como Activa. "
                "No hay «Procesar ahora» en M1."
            )
        elif watch.source_complete:
            modules_note = (
                "Origen listo. Complete disparo (M5) y, si dispara al llegar, enrutado (M4)."
            )
        else:
            modules_note = (
                "En proceso: complete origen (M2) y disparo (M5) para activar. "
                "Editar / Miembros / Archivar viven en el listado."
            )
    elif watch.status == Watch.STATUS_ACTIVE:
        modules_note = (
            "Bandeja activa. Pausar la deja Inactiva; no cancela un Job ya encolado."
        )
    elif watch.status == Watch.STATUS_INACTIVE:
        modules_note = (
            "Inactiva (pausada). Reanudar exige origen (M2) y disparo (M5) válidos "
            "(y enrutado M4 si dispara al llegar)."
        )
    else:
        modules_note = "Archivada: baja lógica. El código no se reutiliza. Solo consulta."

    source_done = watch.source_complete
    intake_done = watch.intake_policy_complete
    route_done = watch.route_complete
    fire_done = watch.fire_complete
    idempotency_done = watch.idempotency_complete
    notify_done = watch.notify_complete
    batches_done = WatchBatch.objects.filter(watch=watch).exists()
    audit_done = batches_done or WatchAuditEvent.objects.filter(watch=watch).exclude(
        event=WatchAuditEvent.EVENT_CREATED
    ).exists()
    members_done = member_count > 1
    (
        source_step_class,
        intake_step_class,
        route_step_class,
        fire_step_class,
        idempotency_step_class,
        notify_step_class,
        batches_step_class,
        audit_step_class,
        members_step_class,
    ) = _stepper_classes(
        [
            source_done,
            intake_done,
            route_done,
            fire_done,
            idempotency_done,
            notify_done,
            batches_done,
            audit_done,
            members_done,
        ]
    )

    return {
        "visibility": watch.visibility,
        "visibility_label": VISIBILITY_LABELS.get(
            watch.visibility, watch.visibility
        ),
        "status": watch.status,
        "status_label": STATUS_LABELS.get(watch.status, watch.status),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == WatchMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": user_can_manage_members(user, watch) and not archived,
        "can_edit": can_edit and not archived,
        "can_pause": can_edit and watch.status == Watch.STATUS_ACTIVE,
        "can_resume": can_edit and watch.status == Watch.STATUS_INACTIVE,
        "can_activate": can_edit
        and watch.status == Watch.STATUS_IN_PROGRESS
        and definition_ready_for_active(watch),
        "can_archive": user_can_archive(user, watch) and not archived,
        "membership": membership,
        "modules_pending_note": modules_note,
        "source_label": _source_label(watch),
        "last_arrival_label": _last_arrival_label(watch),
        "can_create": user_can_create(user),
        "source_complete": source_done,
        "intake_complete": intake_done,
        "route_complete": route_done,
        "fire_complete": fire_done,
        "idempotency_complete": idempotency_done,
        "notify_complete": notify_done,
        "batches_complete": batches_done,
        "audit_complete": audit_done,
        "members_complete": members_done,
        "source_step_class": source_step_class,
        "intake_step_class": intake_step_class,
        "route_step_class": route_step_class,
        "fire_step_class": fire_step_class,
        "idempotency_step_class": idempotency_step_class,
        "notify_step_class": notify_step_class,
        "batches_step_class": batches_step_class,
        "audit_step_class": audit_step_class,
        "members_step_class": members_step_class,
    }


def list_audit_events(watch: Watch):
    return (
        WatchAuditEvent.objects.filter(watch=watch)
        .select_related("actor")
        .order_by("-created_at")
    )


def search_invitable(user, watch: Watch, q: str) -> list[dict]:
    term = (q or "").strip()
    if len(term) < SEARCH_MIN:
        return []
    member_ids = WatchMembership.objects.filter(
        watch=watch,
        is_active=True,
    ).values_list("user_id", flat=True)
    qs = (
        UserProfile.objects.filter(
            company=watch.company,
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


def list_members(watch: Watch):
    return (
        WatchMembership.objects.filter(watch=watch)
        .select_related("user", "invited_by")
        .order_by("created_at")
    )


def invite_member(actor, watch: Watch, data: dict) -> OperationResult:
    if not user_can_manage_members(actor, watch):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)

    user_id = data.get("user_id", "").strip()
    role = resolve_role_code(data.get("role", "").strip()) or ""
    if role not in WatchMembership.WATCH_ROLES:
        role = ""

    errors: dict[str, list[str]] = {}
    if not user_id:
        errors.setdefault("user", []).append("Busque y elija un usuario UF.")
    if not role:
        errors.setdefault("role", []).append("Seleccione un rol válido.")
    if errors:
        return OperationResult.failure(
            "validation_form", "Revise los datos del formulario.", errors=errors
        )

    try:
        profile = UserProfile.objects.select_related("user").get(
            user_id=user_id,
            company=watch.company,
            user_type=UserProfile.USER_FINAL,
        )
    except (UserProfile.DoesNotExist, ValueError):
        return OperationResult.failure(
            "invalid_user",
            "El usuario seleccionado no es válido para esta bandeja.",
            errors={"user": ["Usuario no disponible en su compañía."]},
        )

    if WatchMembership.objects.filter(
        watch=watch,
        user=profile.user,
        is_active=True,
    ).exists():
        return OperationResult.failure(
            "duplicate",
            "El usuario ya es miembro activo de la bandeja.",
            errors={"user": ["Ya tiene membresía activa."]},
        )

    try:
        membership, created = WatchMembership.objects.get_or_create(
            watch=watch,
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
            "invite_watch_member unexpected watch=%s user=%s",
            watch.pk,
            user_id,
        )
        return OperationResult.failure(
            "unexpected", "Ocurrió un error al autorizar el miembro."
        )

    return OperationResult.success(
        user_message=f"Miembro «{profile.user.username}» autorizado correctamente.",
    )


def update_member_role(actor, watch, membership_id: str, role_raw: str) -> OperationResult:
    if not user_can_manage_members(actor, watch):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)
    role = resolve_role_code(role_raw) or ""
    if role not in WatchMembership.WATCH_ROLES:
        return OperationResult.failure("validation_form", "Seleccione un rol válido.")
    try:
        membership = WatchMembership.objects.select_related("user").get(
            pk=membership_id,
            watch=watch,
        )
    except (WatchMembership.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "No se encontró la membresía.")
    if membership.user_id == watch.owner_id:
        return OperationResult.failure(
            "forbidden", "El owner no se revoca ni cambia de rol."
        )
    membership.role = role
    membership.save(update_fields=["role"])
    return OperationResult.success(
        user_message=f"Rol de «{membership.user.username}» actualizado.",
    )


def set_member_active(actor, watch, membership_id: str, *, active: bool) -> OperationResult:
    if not user_can_manage_members(actor, watch):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)
    try:
        membership = WatchMembership.objects.select_related("user").get(
            pk=membership_id,
            watch=watch,
        )
    except (WatchMembership.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "No se encontró la membresía.")
    if membership.user_id == watch.owner_id:
        return OperationResult.failure(
            "forbidden", "El owner no se revoca ni cambia de rol."
        )
    membership.is_active = active
    membership.save(update_fields=["is_active"])
    verb = "reactivado" if active else "revocado"
    return OperationResult.success(
        user_message=f"Acceso de «{membership.user.username}» {verb}.",
    )
