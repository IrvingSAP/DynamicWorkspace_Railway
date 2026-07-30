"""Bridge FILE GATE ↔ FilePipe / Reverse Studio / FILE MATCH.

Config vive en DmsProjectConfig (lado emisor: DMS, Reverse o Match). El pre-check
reutiliza jobs FILE GATE por content_hash; no recalcula el gate (B2 / BR2 / MB-R2).
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

BRIDGEABLE_KINDS = frozenset(
    {Project.KIND_DMS, Project.KIND_REVERSE, Project.KIND_FILE_MATCH}
)

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

MSG_REVERSE = {
    "config_invalid": (
        "La integración FILE GATE está mal configurada. Revise el proyecto vinculado."
    ),
    "gate_not_published": (
        "El proyecto FILE GATE no tiene un contrato publicado. Publique el esquema antes de generar."
    ),
    "no_hash": (
        "La planilla no tiene hash. Vuelva a subirla antes de generar."
    ),
    "no_matching_job": (
        "Valide esta planilla en FILE GATE antes de generar. "
        "No hay una corrida aceptada con el mismo contenido."
    ),
    "status_not_accepted": (
        "La última validación FILE GATE de esta planilla no está aceptada. "
        "Corrija el archivo o revise la evidencia antes de generar."
    ),
    "stale": (
        "La validación FILE GATE de esta planilla expiró por frescura. "
        "Vuelva a validarla en FILE GATE."
    ),
}

MSG_MATCH = {
    "config_invalid": (
        "La integración FILE GATE está mal configurada. Revise el proyecto vinculado."
    ),
    "gate_not_published": (
        "El proyecto FILE GATE no tiene un contrato publicado. "
        "Publique el esquema antes de conciliar."
    ),
    "no_hash": (
        "El archivo {side} no tiene hash. Vuelva a subirlo antes de conciliar."
    ),
    "no_matching_job": (
        "Valide el archivo {side} en FILE GATE antes de conciliar. "
        "No hay una corrida aceptada con el mismo contenido."
    ),
    "status_not_accepted": (
        "La última validación FILE GATE del archivo {side} no está aceptada. "
        "Corrija el archivo o revise la evidencia antes de conciliar."
    ),
    "stale": (
        "La validación FILE GATE del archivo {side} expiró por frescura. "
        "Vuelva a validarlo en FILE GATE."
    ),
    "sides_required": "Marque al menos «Exigir en A» o «Exigir en B».",
}


def is_bridgeable_project(project: Project) -> bool:
    return project.project_kind in BRIDGEABLE_KINDS


def _message(
    code: str,
    project: Project | None = None,
    *,
    side: str | None = None,
) -> str:
    if project is not None and project.project_kind == Project.KIND_REVERSE:
        return MSG_REVERSE.get(code, MSG.get(code, "Pre-check FILE GATE fallido."))
    if project is not None and project.project_kind == Project.KIND_FILE_MATCH:
        template = MSG_MATCH.get(code, MSG.get(code, "Pre-check FILE GATE fallido."))
        return template.format(side=side or "A/B")
    return MSG.get(code, "Pre-check FILE GATE fallido.")


def user_can_configure(user, project: Project) -> bool:
    """PA/ED del proyecto emisor (DMS, Reverse o Match)."""
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
    """Proyectos FILE GATE de la misma compañía (B1 / BR1)."""
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
    """B9 / BR9: aviso suave si los tipos no coinciden."""
    if gate_project is None:
        return ""
    dms_type = _published_file_type(dms_project)
    gate_type = _published_file_type(gate_project)
    if dms_type and gate_type and dms_type != gate_type:
        if dms_project.project_kind == Project.KIND_REVERSE:
            return (
                f"El tipo de archivo del contrato FILE GATE ({gate_type}) "
                f"no coincide con la planilla de entrada ({dms_type})."
            )
        if dms_project.project_kind == Project.KIND_FILE_MATCH:
            return (
                f"El tipo de archivo del contrato FILE GATE ({gate_type}) "
                f"no coincide con el perfil publicado del conciliador ({dms_type})."
            )
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
        "require_a": bool(config.file_gate_require_a),
        "require_b": bool(config.file_gate_require_b),
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
        "is_reverse": dms_project.project_kind == Project.KIND_REVERSE,
        "is_match": dms_project.project_kind == Project.KIND_FILE_MATCH,
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
    if not is_bridgeable_project(dms_project):
        return OperationResult.failure(
            "validation_form",
            "La integración solo aplica a proyectos FilePipe, Reverse Studio o FILE MATCH.",
        )

    errors: dict[str, list[str]] = {}
    enabled = bool(data.get("file_gate_enabled"))
    require_a = bool(data.get("file_gate_require_a"))
    require_b = bool(data.get("file_gate_require_b"))
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

    is_match = dms_project.project_kind == Project.KIND_FILE_MATCH
    if enabled and is_match and not require_a and not require_b:
        errors["file_gate_require_sides"] = [
            _message("sides_required", dms_project)
        ]

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
        gate_project = Project.objects.filter(
            id=gate_id,
            company_id=dms_project.company_id,
            project_kind=Project.KIND_FILE_GATE,
        ).first()
    else:
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
    if is_match:
        config.file_gate_require_a = require_a
        config.file_gate_require_b = require_b
    elif not enabled:
        # Keep require flags as-is for non-match; no-op
        pass

    previous_gate_id = config.file_gate_project_id
    new_gate_id = gate_project.id if gate_project else None
    config.file_gate_project = gate_project
    if new_gate_id and new_gate_id != previous_gate_id:
        config.file_gate_linked_at = timezone.now()
        config.file_gate_linked_by = user
    elif not new_gate_id:
        config.file_gate_linked_at = None
        config.file_gate_linked_by = None

    update_fields = [
        "file_gate_enabled",
        "file_gate_accept",
        "file_gate_max_age_days",
        "file_gate_project",
        "file_gate_linked_at",
        "file_gate_linked_by",
        "updated_at",
    ]
    if is_match:
        update_fields.extend(["file_gate_require_a", "file_gate_require_b"])
    config.save(update_fields=update_fields)

    is_reverse = dms_project.project_kind == Project.KIND_REVERSE
    if enabled:
        user_message = "Integración FILE GATE guardada."
    elif is_match:
        user_message = (
            "Integración FILE GATE desactivada. Conciliar funcionará sin pre-check."
        )
    elif is_reverse:
        user_message = (
            "Integración FILE GATE desactivada. Generar funcionará sin pre-check."
        )
    else:
        user_message = (
            "Integración FILE GATE desactivada. FilePipe ejecutará sin pre-check."
        )
    return OperationResult.success(
        user_message=user_message,
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


def _block(
    code: str,
    *,
    project: Project | None = None,
    gate_project: Project | None = None,
    job=None,
    side: str | None = None,
    **extra,
) -> OperationResult:
    payload = {"links": {}, "side": side or ""}
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
        _message(code, project, side=side),
        **payload,
    )


def _status_accepted(status: str, accept: str) -> bool:
    if accept == ACCEPT_PASSED:
        return status == engine.STATUS_PASSED
    return status in (engine.STATUS_PASSED, engine.STATUS_PASSED_WITH_WARNINGS)


def precheck(
    dms_project: Project,
    *,
    content_hash: str,
    side: str | None = None,
) -> OperationResult:
    """Algoritmo B1–B6 / BR1–BR6 / MB. No recalcula el gate."""
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
        return _block("config_invalid", project=dms_project, side=side)

    if file_intake_persistence_service.get_published_version(gate_project) is None:
        return _block(
            "gate_not_published",
            project=dms_project,
            gate_project=gate_project,
            side=side,
        )

    hash_value = (content_hash or "").strip()
    if not hash_value:
        return _block(
            "no_hash", project=dms_project, gate_project=gate_project, side=side
        )

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
        any_match = (
            DmsExecutionJob.objects.filter(
                project=gate_project,
                input_content_hash=hash_value,
            )
            .exclude(status__in=NON_FINAL_JOB_STATUSES)
            .exists()
        )
        if any_match:
            return _block(
                "stale", project=dms_project, gate_project=gate_project, side=side
            )
        return _block(
            "no_matching_job",
            project=dms_project,
            gate_project=gate_project,
            side=side,
        )

    job = final_jobs[0]
    gate = (job.input_suggestions or {}).get("gate_result") or {}
    status = gate.get("status") or job.status
    accept = config.file_gate_accept or ACCEPT_PASSED_WITH_WARNINGS
    if not _status_accepted(status, accept):
        return _block(
            "status_not_accepted",
            project=dms_project,
            gate_project=gate_project,
            job=job,
            side=side,
        )

    snapshot = gate.get("schema_snapshot") or {}
    version = gate.get("published_version_number") or snapshot.get("version")
    if version is None and job.version_id:
        version = job.version.version_number

    finished = report_svc.job_finished_at(job)
    return OperationResult.success(
        payload={
            "skipped": False,
            "side": side or "",
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
                "side": side or "",
                "checked_at": timezone.now().isoformat().replace("+00:00", "Z"),
            },
        }
    )


def precheck_job(dms_project: Project, job: DmsExecutionJob) -> OperationResult:
    return precheck(dms_project, content_hash=job.input_content_hash or "")


def precheck_match_sides(
    match_project: Project,
    *,
    hash_a: str,
    hash_b: str,
) -> OperationResult:
    """Pre-check dual para FILE MATCH (require_a / require_b)."""
    if match_project.project_kind != Project.KIND_FILE_MATCH:
        return OperationResult.success(payload={"skipped": True})

    config = (
        DmsProjectConfig.objects.select_related("file_gate_project")
        .filter(project_id=match_project.id)
        .first()
    )
    if config is None or not config.file_gate_enabled:
        return OperationResult.success(payload={"skipped": True})

    require_a = bool(config.file_gate_require_a)
    require_b = bool(config.file_gate_require_b)
    if not require_a and not require_b:
        return _block("config_invalid", project=match_project)

    sides: dict = {}
    seal: dict = {}

    if require_a:
        result_a = precheck(match_project, content_hash=hash_a or "", side="A")
        sides["a"] = {
            "ok": result_a.ok,
            "error_code": result_a.error_code,
            "user_message": result_a.user_message,
            **(result_a.payload or {}),
        }
        if not result_a.ok:
            return OperationResult.failure(
                result_a.error_code or "gate_blocked",
                result_a.user_message,
                **{**(result_a.payload or {}), "sides": sides, "failed_side": "A"},
            )
        if not result_a.payload.get("skipped"):
            seal["a"] = result_a.payload.get("seal") or {}

    if require_b:
        result_b = precheck(match_project, content_hash=hash_b or "", side="B")
        sides["b"] = {
            "ok": result_b.ok,
            "error_code": result_b.error_code,
            "user_message": result_b.user_message,
            **(result_b.payload or {}),
        }
        if not result_b.ok:
            return OperationResult.failure(
                result_b.error_code or "gate_blocked",
                result_b.user_message,
                **{**(result_b.payload or {}), "sides": sides, "failed_side": "B"},
            )
        if not result_b.payload.get("skipped"):
            seal["b"] = result_b.payload.get("seal") or {}

    return OperationResult.success(
        payload={
            "skipped": False,
            "sides": sides,
            "seal": seal,
            "require_a": require_a,
            "require_b": require_b,
        }
    )


def stamp_job(job: DmsExecutionJob, seal: dict) -> None:
    """B8 / BR8: sello de auditoría en input_suggestions del job."""
    suggestions = dict(job.input_suggestions or {})
    suggestions["file_gate_check"] = seal
    job.input_suggestions = suggestions
    job.save(update_fields=["input_suggestions", "updated_at"])


def stamp_match_job(job, seal: dict) -> None:
    """MB-R9: sello de auditoría en metrics del FileMatchJob."""
    metrics = dict(job.metrics or {})
    metrics["file_gate_check"] = seal
    job.metrics = metrics
    job.save(update_fields=["metrics"])


def build_hub_context(user, gate_project: Project) -> dict:
    """Hub bridge lado FILE GATE: vínculos entrantes (DMS + Reverse + Match)."""
    from apps.file_match.models import FileMatchJob

    configs = (
        DmsProjectConfig.objects.filter(file_gate_project=gate_project)
        .select_related("project", "file_gate_linked_by")
        .order_by("project__name")
    )
    links = []
    for cfg in configs:
        emitter = cfg.project
        if not is_bridgeable_project(emitter):
            continue

        last_status = ""
        if emitter.project_kind == Project.KIND_FILE_MATCH:
            last_match = (
                FileMatchJob.objects.filter(project=emitter)
                .exclude(status=FileMatchJob.STATUS_RUNNING)
                .order_by("-finished_at", "-created_at")
                .first()
            )
            if last_match is not None:
                seal = (last_match.metrics or {}).get("file_gate_check") or {}
                if isinstance(seal, dict):
                    for key in ("a", "b"):
                        side_seal = seal.get(key) or {}
                        if side_seal.get("gate_status"):
                            last_status = side_seal["gate_status"]
                            break
                    if not last_status:
                        last_status = seal.get("gate_status") or ""
        else:
            last_check = (
                DmsExecutionJob.objects.filter(
                    project=emitter,
                    input_suggestions__has_key="file_gate_check",
                )
                .order_by("-finished_at", "-created_at")
                .first()
            )
            if last_check is not None:
                seal = (last_check.input_suggestions or {}).get("file_gate_check") or {}
                last_status = seal.get("gate_status") or ""

        if emitter.project_kind == Project.KIND_REVERSE:
            settings_url = reverse(
                "reverse_studio:bridge_hub",
                kwargs={"project_slug": emitter.slug},
            )
            execute_url = reverse(
                "reverse_studio:run_hub",
                kwargs={"project_slug": emitter.slug},
            )
            product_label = "Reverse Studio"
            open_label = "Abrir Generar"
            settings_label = "Ajustes Reverse"
        elif emitter.project_kind == Project.KIND_FILE_MATCH:
            settings_url = reverse(
                "file_match:bridge_hub",
                kwargs={"project_slug": emitter.slug},
            )
            execute_url = reverse(
                "file_match:run_hub",
                kwargs={"project_slug": emitter.slug},
            )
            product_label = "FILE MATCH"
            open_label = "Abrir Conciliar"
            settings_label = "Ajustes Match"
        else:
            settings_url = reverse(
                "dms:file_gate_bridge_settings",
                kwargs={"project_slug": emitter.slug},
            )
            execute_url = reverse(
                "dms:transform_execution_hub",
                kwargs={"project_slug": emitter.slug},
            )
            product_label = "FilePipe"
            open_label = "Abrir Ejecutar"
            settings_label = "Ajustes DMS"

        links.append(
            {
                "dms_slug": emitter.slug,
                "dms_name": emitter.name,
                "product_label": product_label,
                "open_label": open_label,
                "settings_label": settings_label,
                "is_reverse": emitter.project_kind == Project.KIND_REVERSE,
                "is_match": emitter.project_kind == Project.KIND_FILE_MATCH,
                "enabled": bool(cfg.file_gate_enabled),
                "require_a": bool(cfg.file_gate_require_a),
                "require_b": bool(cfg.file_gate_require_b),
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
                "settings_url": settings_url,
                "execute_url": execute_url,
            }
        )

    role = report_svc.resolve_role(user, gate_project)
    return {
        "links": links,
        "has_links": bool(links),
        "role": role,
        "is_company_viewer": role == ProjectMembership.ROLE_CO,
    }
