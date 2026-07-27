"""Bridge FILE GATE ↔ FilePipe — Módulo 6 (dms_bridge.md).

Config vive en DmsProjectConfig (lado DMS). El pre-check reutiliza jobs
FILE GATE por content_hash; no recalcula el gate (B2).
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.models import DmsExecutionJob
from apps.dms.file_intake.services import file_intake_persistence_service
from apps.dms.mapping.models import DmsProjectConfig
from apps.file_gate.report.services import validation_report_service as report_svc
from apps.file_gate.run.services import validation_engine_service as engine
from apps.file_gate.run.services import validation_run_service as run_svc
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

DEFAULT_MAX_AGE_DAYS = 7

ACCEPT_PASSED = DmsProjectConfig.ACCEPT_PASSED
ACCEPT_PASSED_WITH_WARNINGS = DmsProjectConfig.ACCEPT_PASSED_WITH_WARNINGS

NON_FINAL_JOB_STATUSES = (
    DmsExecutionJob.STATUS_UPLOADED,
    DmsExecutionJob.STATUS_QUEUED,
    DmsExecutionJob.STATUS_RUNNING,
)

MSG = {
    "config_invalid": (
        "La integración FILE GATE está mal configurada. Revise el proyecto vinculado."
    ),
    "gate_not_published": (
        "El proyecto FILE GATE no tiene un contrato publicado. Publique el esquema antes de transformar."
    ),
    "no_hash": (
        "El archivo de entrada no tiene hash. Vuelva a subirlo antes de transformar."
    ),
    "no_matching_job": (
        "Valide este archivo en FILE GATE antes de transformar. "
        "No hay una corrida aceptada con el mismo contenido."
    ),
    "status_not_accepted": (
        "La última validación FILE GATE de este archivo no está aceptada. "
        "Corrija el archivo o revise la evidencia antes de transformar."
    ),
    "stale": (
        "La validación FILE GATE de este archivo expiró por frescura. "
        "Vuelva a validarlo en FILE GATE."
    ),
}


def user_can_configure(user, project: Project) -> bool:
    """PA/ED del proyecto DMS."""
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
    )


def get_or_create_config(project: Project) -> DmsProjectConfig:
    config, _ = DmsProjectConfig.objects.get_or_create(project=project)
    return config


def list_gate_candidates(dms_project: Project) -> list[dict]:
    """Proyectos FILE GATE de la misma compañía (B1)."""
    qs = (
        Project.objects.filter(
            company_id=dms_project.company_id,
            project_kind=Project.KIND_FILE_GATE,
            is_archived=False,
        )
        .order_by("name")
    )
    return [{"id": str(p.id), "slug": p.slug, "name": p.name} for p in qs]


def _published_file_type(project: Project) -> str:
    published = file_intake_persistence_service.get_published_version(project)
    if published is None:
        return ""
    try:
        return (published.source_profile.file_type_code or "").strip()
    except Exception:
        return ""


def file_type_mismatch_warning(dms_project: Project, gate_project: Project | None) -> str:
    """B9: aviso suave si los tipos no coinciden."""
    if gate_project is None:
        return ""
    dms_type = _published_file_type(dms_project)
    gate_type = _published_file_type(gate_project)
    if dms_type and gate_type and dms_type != gate_type:
        return (
            f"El tipo de archivo del contrato FILE GATE ({gate_type}) "
            f"no coincide con el origen DMS ({dms_type})."
        )
    return ""


def get_settings_context(user, dms_project: Project) -> dict:
    config = get_or_create_config(dms_project)
    gate = config.file_gate_project
    return {
        "can_configure": user_can_configure(user, dms_project),
        "enabled": bool(config.file_gate_enabled),
        "gate_project_id": str(gate.id) if gate_id_safe(gate) else "",
        "gate_project_slug": gate.slug if gate_id_safe(gate) else "",
        "accept": config.file_gate_accept or ACCEPT_PASSED_WITH_WARNINGS,
        "max_age_days": config.file_gate_max_age_days or DEFAULT_MAX_AGE_DAYS,
        "linked_at": config.file_gate_linked_at,
        "linked_by": (
            (
                getattr(config.file_gate_linked_by, "email", None)
                or getattr(config.file_gate_linked_by, "username", "")
            )
            if config.file_gate_linked_by_id
            else ""
        ),
        "candidates": list_gate_candidates(dms_project),
        "file_type_warning": file_type_mismatch_warning(dms_project, gate),
        "accept_choices": [
            {"value": ACCEPT_PASSED, "label": "Solo passed"},
            {
                "value": ACCEPT_PASSED_WITH_WARNINGS,
                "label": "passed o passed_with_warnings",
            },
        ],
    }


def gate_id_safe(gate: Project | None) -> bool:
    return gate is not None and gate.project_kind == Project.KIND_FILE_GATE


@transaction.atomic
def save_settings(user, dms_project: Project, data: dict) -> OperationResult:
    if not user_can_configure(user, dms_project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para configurar la integración FILE GATE.",
        )
    if dms_project.project_kind != Project.KIND_DMS:
        return OperationResult.failure(
            "validation_form",
            "La integración solo aplica a proyectos FilePipe (DMS).",
        )

    errors: dict[str, list[str]] = {}
    enabled = bool(data.get("file_gate_enabled"))
    gate_id = (data.get("file_gate_project_id") or "").strip()
    accept = (data.get("file_gate_accept") or ACCEPT_PASSED_WITH_WARNINGS).strip()
    if accept not in (ACCEPT_PASSED, ACCEPT_PASSED_WITH_WARNINGS):
        errors["file_gate_accept"] = ["Política de aceptación inválida."]
        accept = ACCEPT_PASSED_WITH_WARNINGS

    max_age_raw = (data.get("file_gate_max_age_days") or "").strip()
    try:
        max_age = int(max_age_raw) if max_age_raw else DEFAULT_MAX_AGE_DAYS
    except ValueError:
        max_age = 0
    if max_age < 1:
        errors["file_gate_max_age_days"] = ["La frescura debe ser un número ≥ 1."]
        max_age = DEFAULT_MAX_AGE_DAYS

    gate_project = None
    if enabled:
        if not gate_id:
            errors["file_gate_project_id"] = ["Elija un proyecto FILE GATE."]
        else:
            gate_project = Project.objects.filter(
                id=gate_id,
                company_id=dms_project.company_id,
                project_kind=Project.KIND_FILE_GATE,
            ).first()
            if gate_project is None:
                errors["file_gate_project_id"] = [
                    "Proyecto FILE GATE inválido o de otra compañía."
                ]
    elif gate_id:
        # B7: puede conservar el vínculo aunque el flag esté OFF.
        gate_project = Project.objects.filter(
            id=gate_id,
            company_id=dms_project.company_id,
            project_kind=Project.KIND_FILE_GATE,
        ).first()
    else:
        # Flag OFF y sin selección → conservar el vínculo previo (B7).
        config_preview = get_or_create_config(dms_project)
        gate_project = config_preview.file_gate_project
        if gate_project is not None and (
            gate_project.company_id != dms_project.company_id
            or gate_project.project_kind != Project.KIND_FILE_GATE
        ):
            gate_project = None

    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los campos de la integración FILE GATE.",
            errors=errors,
        )

    config = get_or_create_config(dms_project)
    config.file_gate_enabled = enabled
    config.file_gate_accept = accept
    config.file_gate_max_age_days = max_age

    previous_gate_id = config.file_gate_project_id
    new_gate_id = gate_project.id if gate_project else None
    config.file_gate_project = gate_project
    if new_gate_id and new_gate_id != previous_gate_id:
        config.file_gate_linked_at = timezone.now()
        config.file_gate_linked_by = user
    elif not new_gate_id:
        config.file_gate_linked_at = None
        config.file_gate_linked_by = None

    config.save()
    return OperationResult.success(
        user_message=(
            "Integración FILE GATE guardada."
            if enabled
            else "Integración FILE GATE desactivada. FilePipe ejecutará sin pre-check."
        ),
        payload={"config_id": str(config.id)},
    )


def _gate_links(gate_project: Project, job: DmsExecutionJob | None = None) -> dict:
    links = {
        "validate": reverse(
            "file_gate:run_upload", kwargs={"project_slug": gate_project.slug}
        ),
        "history": reverse(
            "file_gate:history_hub", kwargs={"project_slug": gate_project.slug}
        ),
        "bridge": reverse(
            "file_gate:bridge_hub", kwargs={"project_slug": gate_project.slug}
        ),
        "run_hub": reverse(
            "file_gate:run_hub", kwargs={"project_slug": gate_project.slug}
        ),
    }
    if job is not None:
        links["result"] = reverse(
            "file_gate:run_result",
            kwargs={"project_slug": gate_project.slug, "job_id": job.id},
        )
        links["report"] = reverse(
            "file_gate:report_detail",
            kwargs={"project_slug": gate_project.slug, "job_id": job.id},
        )
        links["certificate"] = reverse(
            "file_gate:report_certificate",
            kwargs={"project_slug": gate_project.slug, "job_id": job.id},
        )
    return links


def _block(code: str, *, gate_project: Project | None = None, job=None, **extra) -> OperationResult:
    payload = {"links": {}}
    if gate_project is not None:
        payload["links"] = _gate_links(gate_project, job)
        payload["gate_project_slug"] = gate_project.slug
    if job is not None:
        payload["gate_job_id"] = str(job.id)
        gate = (job.input_suggestions or {}).get("gate_result") or {}
        payload["gate_status"] = gate.get("status") or job.status
    payload.update(extra)
    return OperationResult.failure(
        code,
        MSG.get(code, "Pre-check FILE GATE fallido."),
        **payload,
    )


def _status_accepted(status: str, accept: str) -> bool:
    if accept == ACCEPT_PASSED:
        return status == engine.STATUS_PASSED
    return status in (engine.STATUS_PASSED, engine.STATUS_PASSED_WITH_WARNINGS)


def precheck(dms_project: Project, *, content_hash: str) -> OperationResult:
    """Algoritmo B1–B6 / D3–D5. No recalcula el gate."""
    config = (
        DmsProjectConfig.objects.select_related("file_gate_project")
        .filter(project_id=dms_project.id)
        .first()
    )
    if config is None or not config.file_gate_enabled:
        return OperationResult.success(payload={"skipped": True})

    gate_project = config.file_gate_project
    if (
        gate_project is None
        or gate_project.project_kind != Project.KIND_FILE_GATE
        or gate_project.company_id != dms_project.company_id
    ):
        return _block("config_invalid")

    if file_intake_persistence_service.get_published_version(gate_project) is None:
        return _block("gate_not_published", gate_project=gate_project)

    hash_value = (content_hash or "").strip()
    if not hash_value:
        return _block("no_hash", gate_project=gate_project)

    max_age = config.file_gate_max_age_days or DEFAULT_MAX_AGE_DAYS
    cutoff = timezone.now() - timedelta(days=max_age)

    candidates = list(
        DmsExecutionJob.objects.filter(
            project=gate_project,
            input_content_hash=hash_value,
        )
        .exclude(status__in=NON_FINAL_JOB_STATUSES)
        .annotate(effective_at=Coalesce("finished_at", "created_at"))
        .filter(effective_at__gte=cutoff)
        .order_by("-effective_at", "-created_at")[:40]
    )

    final_jobs = [job for job in candidates if report_svc.is_job_final(job)]
    if not final_jobs:
        # Distinguir frescura: ¿hay job matching pero viejo?
        any_match = (
            DmsExecutionJob.objects.filter(
                project=gate_project,
                input_content_hash=hash_value,
            )
            .exclude(status__in=NON_FINAL_JOB_STATUSES)
            .exists()
        )
        if any_match:
            return _block("stale", gate_project=gate_project)
        return _block("no_matching_job", gate_project=gate_project)

    job = final_jobs[0]
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    status = gate.get("status") or job.status
    accept = config.file_gate_accept or ACCEPT_PASSED_WITH_WARNINGS
    if not _status_accepted(status, accept):
        return _block("status_not_accepted", gate_project=gate_project, job=job)

    snapshot = gate.get("schema_snapshot") or {}
    version = gate.get("published_version_number") or snapshot.get("version")
    if version is None and job.version_id:
        version = job.version.version_number

    finished = report_svc.job_finished_at(job)
    return OperationResult.success(
        payload={
            "skipped": False,
            "gate_project_slug": gate_project.slug,
            "gate_project_id": str(gate_project.id),
            "gate_job_id": str(job.id),
            "gate_status": status,
            "gate_status_label": run_svc.GATE_STATUS_LABELS.get(status, status),
            "gate_tone": run_svc.GATE_STATUS_TONE.get(status, "passed"),
            "content_hash": hash_value,
            "finished_at": finished,
            "published_version": version,
            "links": _gate_links(gate_project, job),
            "file_type_warning": file_type_mismatch_warning(dms_project, gate_project),
            "seal": {
                "gate_project_slug": gate_project.slug,
                "gate_job_id": str(job.id),
                "gate_status": status,
                "content_hash": f"sha256:{hash_value}" if hash_value else "",
                "checked_at": timezone.now().isoformat().replace("+00:00", "Z"),
            },
        }
    )


def precheck_job(dms_project: Project, job: DmsExecutionJob) -> OperationResult:
    return precheck(dms_project, content_hash=job.input_content_hash or "")


def stamp_job(job: DmsExecutionJob, seal: dict) -> None:
    """B8: sello de auditoría en input_suggestions del job DMS."""
    suggestions = dict(job.input_suggestions or {})
    suggestions["file_gate_check"] = seal
    job.input_suggestions = suggestions
    job.save(update_fields=["input_suggestions", "updated_at"])


def build_hub_context(user, gate_project: Project) -> dict:
    """Hub bridge lado FILE GATE: vínculos entrantes."""
    configs = (
        DmsProjectConfig.objects.filter(file_gate_project=gate_project)
        .select_related("project", "file_gate_linked_by")
        .order_by("project__name")
    )
    links = []
    for cfg in configs:
        dms = cfg.project
        if dms.project_kind != Project.KIND_DMS:
            continue
        last_check = (
            DmsExecutionJob.objects.filter(
                project=dms,
                input_suggestions__has_key="file_gate_check",
            )
            .order_by("-finished_at", "-created_at")
            .first()
        )
        last_status = ""
        if last_check is not None:
            seal = (last_check.input_suggestions or {}).get("file_gate_check") or {}
            last_status = seal.get("gate_status") or ""
        links.append(
            {
                "dms_slug": dms.slug,
                "dms_name": dms.name,
                "enabled": bool(cfg.file_gate_enabled),
                "accept": cfg.file_gate_accept,
                "max_age_days": cfg.file_gate_max_age_days,
                "linked_at": cfg.file_gate_linked_at,
                "linked_by": (
                    (
                        getattr(cfg.file_gate_linked_by, "email", None)
                        or getattr(cfg.file_gate_linked_by, "username", "")
                    )
                    if cfg.file_gate_linked_by_id
                    else ""
                ),
                "last_status": last_status,
                "settings_url": reverse(
                    "dms:file_gate_bridge_settings",
                    kwargs={"project_slug": dms.slug},
                ),
                "execute_url": reverse(
                    "dms:transform_execution_hub",
                    kwargs={"project_slug": dms.slug},
                ),
            }
        )

    role = report_svc.resolve_role(user, gate_project)
    return {
        "links": links,
        "has_links": bool(links),
        "role": role,
        "is_company_viewer": role == ProjectMembership.ROLE_CO,
    }
