"""M1 File Pipeline: definición, listado, hub, miembros."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import Max, Q

from apps.accounts.models import UserProfile
from apps.core.services.operation_result import OperationResult
from apps.dms.catalogs.services.permission_package_service import resolve_role_code
from apps.file_pipeline.models import PipelineDefinition, PipelineMembership, PipelineRun
from apps.projects.services.project_service import SLUG_RE, find_project_by_slug, slug_duplicate_message

logger = logging.getLogger(__name__)

VISIBILITY_LABELS = {
    PipelineDefinition.VISIBILITY_COMPANY: "Público",
    PipelineDefinition.VISIBILITY_MEMBERS_ONLY: "Privado",
}

STATUS_LABELS = {
    PipelineDefinition.STATUS_ACTIVE: "Activo",
    PipelineDefinition.STATUS_IN_PROGRESS: "En proceso",
    PipelineDefinition.STATUS_INACTIVE: "Inactivo",
}

ROLE_LABELS = {
    PipelineMembership.ROLE_PA: "PA — Admin",
    PipelineMembership.ROLE_ED: "ED — Editor",
    PipelineMembership.ROLE_GE: "GE — Ejecutor",
    PipelineMembership.ROLE_CO: "CO — Consulta",
    "company_viewer": "CO — Consulta (compañía)",
}

DEFAULT_DESCRIPTION = "Pipeline: orquestación de flujos multi-app."

MSG_NO_ACCESS = "No tiene acceso a este pipeline."
MSG_UF_ONLY = "Solo usuarios UF pueden crear pipelines."
MSG_CREATED = "Pipeline creado correctamente."
MSG_PA_ONLY = "Solo el administrador del pipeline (PA) puede gestionar miembros."
MSG_PUBLISH_BLOCKED = "No puede publicar. Pasos no completados: Diseñar pasos."
MSG_STATUS_UPDATED = "Estado del pipeline actualizado."

SEARCH_LIMIT = 20
SEARCH_MIN = 2


def get_membership(user, pipeline: PipelineDefinition) -> PipelineMembership | None:
    return (
        PipelineMembership.objects.filter(
            pipeline=pipeline,
            user=user,
            is_active=True,
        )
        .select_related("user")
        .first()
    )


def user_can_view(user, pipeline: PipelineDefinition) -> bool:
    if pipeline.company_id != user.profile.company_id:
        return False
    if get_membership(user, pipeline) is not None:
        return True
    return pipeline.visibility == PipelineDefinition.VISIBILITY_COMPANY


def user_can_manage_members(user, pipeline: PipelineDefinition) -> bool:
    membership = get_membership(user, pipeline)
    return membership is not None and membership.role == PipelineMembership.ROLE_PA


def set_pipeline_status(user, pipeline: PipelineDefinition, status: str) -> OperationResult:
    if not user_can_manage_members(user, pipeline):
        return OperationResult.failure(
            "forbidden",
            "Solo el administrador del pipeline (PA) puede cambiar el estado.",
        )
    if status not in dict(PipelineDefinition.STATUS_CHOICES):
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"status": ["Estado no válido."]},
        )
    pipeline.status = status
    pipeline.save(update_fields=["status", "updated_at"])
    return OperationResult.success(user_message=MSG_STATUS_UPDATED)



def get_pipeline_for_user(user, slug: str) -> PipelineDefinition | None:
    try:
        pipeline = PipelineDefinition.objects.select_related(
            "company", "owner", "current_version"
        ).get(
            company=user.profile.company,
            slug=slug,
        )
    except PipelineDefinition.DoesNotExist:
        return None
    if not user_can_view(user, pipeline):
        return None
    return pipeline


def visible_qs(user):
    company = user.profile.company
    member_ids = PipelineMembership.objects.filter(
        user=user,
        is_active=True,
        pipeline__company=company,
    ).values_list("pipeline_id", flat=True)
    return (
        PipelineDefinition.objects.filter(company=company)
        .filter(
            Q(id__in=member_ids)
            | Q(visibility=PipelineDefinition.VISIBILITY_COMPANY)
        )
        .select_related("owner")
        .distinct()
    )


def _role_for_row(user, pipeline: PipelineDefinition) -> tuple[str | None, str]:
    membership = get_membership(user, pipeline)
    if membership is not None:
        return membership.role, ROLE_LABELS.get(membership.role, membership.role)
    return None, ROLE_LABELS["company_viewer"]


def format_step_chain(labels) -> dict:
    parts = [str(x) for x in (labels or []) if str(x).strip()]
    if not parts:
        return {"full": "—", "short": "—", "truncated": False}
    full = " → ".join(parts)
    if len(parts) <= 2:
        return {"full": full, "short": full, "truncated": False}
    return {
        "full": full,
        "short": f"{parts[0]} → {parts[1]}",
        "truncated": True,
    }


def format_last_run_label(run: PipelineRun | None) -> str:
    if run is None:
        return "—"
    label = run.get_status_display()
    if run.dry_run:
        label = f"{label} · dry-run"
    if run.created_at:
        label = f"{label} · {run.created_at:%d/%m %H:%M}"
    return label


def _latest_runs_by_pipeline(pipeline_ids: list) -> dict:
    if not pipeline_ids:
        return {}
    pairs = list(
        PipelineRun.objects.filter(pipeline_id__in=pipeline_ids)
        .values("pipeline_id")
        .annotate(latest_at=Max("created_at"))
    )
    if not pairs:
        return {}
    match = Q()
    for row in pairs:
        match |= Q(pipeline_id=row["pipeline_id"], created_at=row["latest_at"])
    latest: dict = {}
    for run in PipelineRun.objects.filter(match).order_by("-created_at"):
        if run.pipeline_id not in latest:
            latest[run.pipeline_id] = run
    return latest


def list_with_stats(user, *, q: str = "", status: str = "all"):
    qs = visible_qs(user).order_by("-updated_at")
    term = (q or "").strip()
    if term:
        qs = qs.filter(Q(slug__icontains=term) | Q(name__icontains=term))
    if status in {
        PipelineDefinition.STATUS_ACTIVE,
        PipelineDefinition.STATUS_IN_PROGRESS,
        PipelineDefinition.STATUS_INACTIVE,
    }:
        qs = qs.filter(status=status)

    pipelines = list(qs.select_related("current_version"))
    latest_run_by_pipeline = _latest_runs_by_pipeline([p.id for p in pipelines])
    rows = []
    for pipeline in pipelines:
        role_code, role_label = _role_for_row(user, pipeline)
        chain = format_step_chain(pipeline.draft_step_labels)
        published = pipeline.current_version
        rows.append(
            {
                "pipeline": pipeline,
                "role": role_code,
                "role_label": role_label,
                "visibility": pipeline.visibility,
                "visibility_label": VISIBILITY_LABELS.get(
                    pipeline.visibility, pipeline.visibility
                ),
                "status": pipeline.status,
                "status_label": STATUS_LABELS.get(pipeline.status, pipeline.status),
                "step_chain": chain,
                "version_label": (
                    f"v{published.version_number}"
                    if published is not None
                    else "Sin publicar"
                ),
                "last_run_label": format_last_run_label(
                    latest_run_by_pipeline.get(pipeline.id)
                ),
                "is_pa": role_code == PipelineMembership.ROLE_PA,
            }
        )

    stats = {
        "total": len(rows),
        "active": sum(
            1 for row in rows if row["status"] == PipelineDefinition.STATUS_ACTIVE
        ),
        "in_progress": sum(
            1
            for row in rows
            if row["status"] == PipelineDefinition.STATUS_IN_PROGRESS
        ),
        "inactive": sum(
            1 for row in rows if row["status"] == PipelineDefinition.STATUS_INACTIVE
        ),
    }
    return rows, stats


def default_posted() -> dict:
    return {
        "name": "",
        "slug": "",
        "description": "",
        "visibility": PipelineDefinition.VISIBILITY_MEMBERS_ONLY,
    }


def posted_from_request(post) -> dict:
    return {
        "name": post.get("name", "").strip(),
        "slug": post.get("slug", "").strip().lower(),
        "description": post.get("description", "").strip(),
        "visibility": post.get("visibility", "").strip(),
    }


def validate_create_data(data: dict, company) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    name = data.get("name", "").strip()
    if not name:
        errors.setdefault("name", []).append("Ingrese el nombre del pipeline.")
    elif len(name) > 200:
        errors.setdefault("name", []).append("Máximo 200 caracteres.")

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

    description = data.get("description", "")
    if len(description) > 5000:
        errors.setdefault("description", []).append("La descripción es demasiado larga.")

    visibility = data.get("visibility", "")
    valid_vis = {c[0] for c in PipelineDefinition.VISIBILITY_CHOICES}
    if visibility not in valid_vis:
        errors.setdefault("visibility", []).append("Seleccione una visibilidad válida.")
    return errors


def create_pipeline(user, data: dict) -> OperationResult:
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
            pipeline = PipelineDefinition.objects.create(
                company=company,
                name=data["name"],
                slug=data["slug"],
                description=description,
                owner=user,
                visibility=data["visibility"],
                status=PipelineDefinition.STATUS_IN_PROGRESS,
            )
            PipelineMembership.objects.create(
                pipeline=pipeline,
                user=user,
                role=PipelineMembership.ROLE_PA,
                invited_by=None,
                is_active=True,
            )
    except IntegrityError:
        logger.exception("create_pipeline IntegrityError slug=%s", data.get("slug"))
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"slug": ["Ya existe un pipeline con este código en su compañía."]},
        )
    except Exception:
        logger.exception("create_pipeline unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message=MSG_CREATED,
        payload={"pipeline": pipeline},
    )


def get_hub_context(user, pipeline: PipelineDefinition) -> dict:
    membership = get_membership(user, pipeline)
    role_code, role_label = _role_for_row(user, pipeline)
    member_count = PipelineMembership.objects.filter(
        pipeline=pipeline,
        is_active=True,
    ).count()
    design_complete = pipeline.design_complete
    chain = format_step_chain(pipeline.draft_step_labels)
    published = pipeline.current_version
    has_published = published is not None
    version_label = (
        f"v{published.version_number} publicada" if has_published else "Sin publicar"
    )

    last = PipelineRun.objects.filter(pipeline=pipeline).order_by("-created_at").first()
    last_run_label = format_last_run_label(last)

    run_complete = last is not None

    if design_complete:
        design_step_class = "is-done"
    else:
        design_step_class = "is-active"

    if has_published:
        publish_step_class = "is-done"
    elif design_complete:
        publish_step_class = "is-active"
    else:
        publish_step_class = "is-pending"

    if run_complete:
        run_step_class = "is-done"
    elif has_published:
        run_step_class = "is-active"
    else:
        run_step_class = "is-pending"

    if run_complete:
        history_step_class = "is-done"
    else:
        history_step_class = "is-pending"

    run_blocked = ""
    if not has_published:
        run_blocked = "No puede ejecutar. Publique una versión primero."
    elif pipeline.status != PipelineDefinition.STATUS_ACTIVE:
        run_blocked = "El pipeline debe estar Activo para ejecutar."

    if not design_complete:
        modules_note = (
            "Guarde el rail en el diseñador con al menos un paso para poder publicar."
        )
    elif not has_published:
        modules_note = "Diseño listo. Publique una versión para ejecutar."
    elif pipeline.status != PipelineDefinition.STATUS_ACTIVE:
        modules_note = "Versión publicada. Márquelo Activo (PA) y ejecute."
    elif last is None:
        modules_note = "Listo para ejecutar la versión publicada."
    else:
        modules_note = "Consulte el historial para auditar disparo, versión y pasos."

    return {
        "visibility": pipeline.visibility,
        "visibility_label": VISIBILITY_LABELS.get(
            pipeline.visibility, pipeline.visibility
        ),
        "status": pipeline.status,
        "status_label": STATUS_LABELS.get(pipeline.status, pipeline.status),
        "role": role_code,
        "role_label": role_label,
        "is_pa": role_code == PipelineMembership.ROLE_PA,
        "member_count": member_count,
        "can_manage_members": user_can_manage_members(user, pipeline),
        "can_edit_design": membership is not None
        and membership.role
        in {PipelineMembership.ROLE_PA, PipelineMembership.ROLE_ED},
        "design_complete": design_complete,
        "has_published_version": has_published,
        "run_complete": run_complete,
        "step_chain": chain,
        "version_label": version_label,
        "last_run_label": last_run_label,
        "design_step_class": design_step_class,
        "publish_step_class": publish_step_class,
        "run_step_class": run_step_class,
        "history_step_class": history_step_class,
        "can_open_run": has_published,
        "run_blocked_message": run_blocked,
        "membership": membership,
        "publish_blocked_message": MSG_PUBLISH_BLOCKED,
        "modules_pending_note": modules_note,
    }


def search_invitable(user, pipeline: PipelineDefinition, q: str) -> list[dict]:
    term = (q or "").strip()
    if len(term) < SEARCH_MIN:
        return []
    member_ids = PipelineMembership.objects.filter(
        pipeline=pipeline,
        is_active=True,
    ).values_list("user_id", flat=True)
    qs = (
        UserProfile.objects.filter(
            company=pipeline.company,
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


def list_members(pipeline: PipelineDefinition):
    return (
        PipelineMembership.objects.filter(pipeline=pipeline)
        .select_related("user", "invited_by")
        .order_by("created_at")
    )


def invite_member(actor, pipeline: PipelineDefinition, data: dict) -> OperationResult:
    if not user_can_manage_members(actor, pipeline):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)

    user_id = data.get("user_id", "").strip()
    role = resolve_role_code(data.get("role", "").strip()) or ""
    if role not in PipelineMembership.PIPELINE_ROLES:
        role = ""

    errors: dict[str, list[str]] = {}
    if not user_id:
        errors.setdefault("user", []).append("Busque y elija un usuario UF.")
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
            company=pipeline.company,
            user_type=UserProfile.USER_FINAL,
        )
    except (UserProfile.DoesNotExist, ValueError):
        return OperationResult.failure(
            "invalid_user",
            "El usuario seleccionado no es válido para este pipeline.",
            errors={"user": ["Usuario no disponible en su compañía."]},
        )

    if PipelineMembership.objects.filter(
        pipeline=pipeline,
        user=profile.user,
        is_active=True,
    ).exists():
        return OperationResult.failure(
            "duplicate",
            "El usuario ya es miembro activo del pipeline.",
            errors={"user": ["Ya tiene membresía activa."]},
        )

    try:
        membership, created = PipelineMembership.objects.get_or_create(
            pipeline=pipeline,
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
            "invite_pipeline_member unexpected pipeline=%s user=%s",
            pipeline.pk,
            user_id,
        )
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al autorizar el miembro.",
        )

    return OperationResult.success(
        user_message=f"Miembro «{profile.user.username}» autorizado correctamente.",
    )


def update_member_role(actor, pipeline, membership_id: str, role_raw: str) -> OperationResult:
    if not user_can_manage_members(actor, pipeline):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)
    role = resolve_role_code(role_raw) or ""
    if role not in PipelineMembership.PIPELINE_ROLES:
        return OperationResult.failure("validation_form", "Seleccione un rol válido.")
    try:
        membership = PipelineMembership.objects.select_related("user").get(
            pk=membership_id,
            pipeline=pipeline,
        )
    except (PipelineMembership.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "No se encontró la membresía.")
    if membership.user_id == pipeline.owner_id:
        return OperationResult.failure(
            "forbidden",
            "El owner no se revoca ni cambia de rol.",
        )
    membership.role = role
    membership.save(update_fields=["role"])
    return OperationResult.success(
        user_message=f"Rol de «{membership.user.username}» actualizado.",
    )


def set_member_active(actor, pipeline, membership_id: str, *, active: bool) -> OperationResult:
    if not user_can_manage_members(actor, pipeline):
        return OperationResult.failure("forbidden", MSG_PA_ONLY)
    try:
        membership = PipelineMembership.objects.select_related("user").get(
            pk=membership_id,
            pipeline=pipeline,
        )
    except (PipelineMembership.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "No se encontró la membresía.")
    if membership.user_id == pipeline.owner_id:
        return OperationResult.failure(
            "forbidden",
            "El owner no se revoca ni cambia de rol.",
        )
    membership.is_active = active
    membership.save(update_fields=["is_active"])
    verb = "reactivado" if active else "revocado"
    return OperationResult.success(
        user_message=f"Acceso de «{membership.user.username}» {verb}.",
    )
