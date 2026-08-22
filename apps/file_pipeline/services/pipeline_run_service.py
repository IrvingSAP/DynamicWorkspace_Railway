"""Ejecutar versión publicada de File Pipeline (M4)."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.services import (
    file_intake_persistence_service,
    storage_service,
)
from apps.dms.transform_execution.services import execution_service as dms_exec
from apps.file_clean.run.services import clean_run_service
from apps.file_gate.run.services import validation_engine_service as gate_engine
from apps.file_gate.run.services import validation_run_service as gate_run
from apps.file_pipeline.models import (
    PipelineDefinition,
    PipelineMembership,
    PipelineRun,
    PipelineStepRun,
)
from apps.file_pipeline.services import pipeline_project_service as lifecycle
from apps.file_split_merge.run.services import sm_run_service
from apps.projects.models import Project as ProjectModel
from apps.projects.models import ProjectMembership

logger = logging.getLogger(__name__)

MSG_NO_VERSION = "No hay versión publicada. Publique el pipeline antes de ejecutar."
MSG_NOT_ACTIVE = "El pipeline debe estar Activo para ejecutar."
MSG_NO_FILE = "Seleccione un archivo de entrada."
MSG_NO_RUN = "No tiene permiso para ejecutar este pipeline."
MSG_NO_STEP_PERM = "No tiene permiso para ejecutar uno de los proyectos de paso."
MSG_KIND_UNSUPPORTED = "Este tipo de paso aún no tiene runner en el orquestador."
MSG_EMPTY = "El archivo está vacío."
MSG_OK = "Corrida completada."
MSG_FAIL = "La corrida falló. Revise el rail de pasos."
MSG_ACTIVATED = "Pipeline marcado como Activo."


def user_can_execute_pipeline(user, pipeline: PipelineDefinition) -> bool:
    membership = lifecycle.get_membership(user, pipeline)
    if membership is None:
        return False
    return membership.role in {
        PipelineMembership.ROLE_PA,
        PipelineMembership.ROLE_ED,
        PipelineMembership.ROLE_GE,
    }


def _project_can_execute(user, project) -> bool:
    membership = ProjectMembership.objects.filter(
        project=project, user=user, is_active=True
    ).first()
    if membership is None:
        return False
    return ProjectMembership.role_can_execute(membership.role)


def run_gate_reason(pipeline: PipelineDefinition, user) -> str:
    if pipeline.current_version_id is None:
        return MSG_NO_VERSION
    if pipeline.status != PipelineDefinition.STATUS_ACTIVE:
        return MSG_NOT_ACTIVE
    if not user_can_execute_pipeline(user, pipeline):
        return MSG_NO_RUN
    return ""


def latest_run(pipeline: PipelineDefinition) -> PipelineRun | None:
    return pipeline.runs.order_by("-created_at").first()


def get_run(pipeline: PipelineDefinition, run_id) -> PipelineRun | None:
    return (
        PipelineRun.objects.filter(pipeline=pipeline, id=run_id)
        .select_related("version", "triggered_by")
        .prefetch_related("steps")
        .first()
    )


def _sha256_upload(uploaded) -> str:
    digest = hashlib.sha256()
    if hasattr(uploaded, "chunks"):
        for chunk in uploaded.chunks():
            digest.update(chunk)
        if hasattr(uploaded, "seek"):
            try:
                uploaded.seek(0)
            except Exception:
                pass
    else:
        data = uploaded.read()
        digest.update(data)
        if hasattr(uploaded, "seek"):
            uploaded.seek(0)
    return digest.hexdigest()


def _wrap_stored(stored_path: str, filename: str):
    abs_path = storage_service.absolute_from_stored(stored_path)
    name = filename or abs_path.name
    return SimpleUploadedFile(name, abs_path.read_bytes())


def _job_url(kind: str, project_slug: str, job_id: str) -> str:
    try:
        if kind == "file_clean":
            return reverse(
                "file_clean:run_result",
                kwargs={"project_slug": project_slug, "job_id": job_id},
            )
        if kind == "file_gate":
            return reverse(
                "file_gate:run_result",
                kwargs={"project_slug": project_slug, "job_id": job_id},
            )
        if kind in {"file_split", "file_merge"}:
            return reverse(
                "file_split_merge:run_result",
                kwargs={"project_slug": project_slug, "job_id": job_id},
            )
        if kind == "dms":
            return reverse(
                "dms:transform_execution_hub",
                kwargs={"project_slug": project_slug},
            )
    except Exception:
        return ""
    return ""


def _invoke_step(user, kind: str, project, upload, *, dry_run: bool) -> dict:
    """Devuelve dict ok, job_id, message, error_code, handoff {stored_path, filename}, artifacts."""
    if kind == "file_clean":
        result = clean_run_service.run_clean_job(
            user, project, None, upload, dry_run=dry_run
        )
        job = (result.payload or {}).get("job")
        job_id = str(getattr(job, "id", "") or "")
        handoff = None
        if result.ok and job is not None and getattr(job, "output_stored_path", ""):
            handoff = {
                "stored_path": job.output_stored_path,
                "filename": job.output_filename or "clean_output",
            }
        return {
            "ok": bool(result.ok),
            "job_id": job_id,
            "message": result.user_message,
            "error_code": result.error_code or "",
            "handoff": handoff,
            "artifacts": [{"role": "output", "path": getattr(job, "output_stored_path", "")}]
            if job
            else [],
        }

    if kind == "file_gate":
        result = gate_run.validate_and_run(user, project, upload)
        job = (result.payload or {}).get("job")
        job_id = str(getattr(job, "id", "") or "")
        gate_status = (result.payload or {}).get("gate_status") or ""
        passed = gate_status in {
            gate_engine.STATUS_PASSED,
            gate_engine.STATUS_PASSED_WITH_WARNINGS,
        }
        ok = bool(result.ok) and passed
        handoff = None
        if job is not None and getattr(job, "input_stored_path", ""):
            handoff = {
                "stored_path": job.input_stored_path,
                "filename": job.input_original_filename or "file",
            }
        return {
            "ok": ok,
            "job_id": job_id,
            "message": result.user_message,
            "error_code": "" if ok else (gate_status or result.error_code or "gate_failed"),
            "handoff": handoff if ok else None,
            "artifacts": [{"role": "report", "path": getattr(job, "report_path", "")}]
            if job
            else [],
        }

    if kind in {"file_split", "file_merge"}:
        files = [upload]
        result = sm_run_service.run_sm_job(user, project, files, dry_run=dry_run)
        job = (result.payload or {}).get("job")
        job_id = str(getattr(job, "id", "") or "")
        handoff = None
        artifacts = []
        if job is not None:
            for item in job.outputs or []:
                artifacts.append(
                    {
                        "role": item.get("kind") or "output",
                        "path": item.get("stored_path") or "",
                        "filename": item.get("filename") or "",
                    }
                )
            for item in job.outputs or []:
                path = item.get("stored_path") or ""
                if not path:
                    continue
                role = (item.get("kind") or "").lower()
                if role in {"zip", "archive"}:
                    continue
                handoff = {
                    "stored_path": path,
                    "filename": item.get("filename") or "sm_output",
                }
                break
            if handoff is None and artifacts:
                handoff = {
                    "stored_path": artifacts[0]["path"],
                    "filename": artifacts[0].get("filename") or "sm_output",
                }
        return {
            "ok": bool(result.ok),
            "job_id": job_id,
            "message": result.user_message,
            "error_code": result.error_code or "",
            "handoff": handoff if result.ok else None,
            "artifacts": artifacts,
        }

    if kind == "dms":
        up = file_intake_persistence_service.upload_production(user, project, upload)
        if not up.ok:
            job = (up.payload or {}).get("job")
            return {
                "ok": False,
                "job_id": str(getattr(job, "id", "") or ""),
                "message": up.user_message,
                "error_code": up.error_code or "",
                "handoff": None,
                "artifacts": [],
            }
        job = up.payload["job"]
        exec_result = dms_exec.run_full_job(user, project, job.id)
        job = (exec_result.payload or {}).get("job") or job
        if hasattr(job, "refresh_from_db"):
            job.refresh_from_db()
        dms_ok = bool(exec_result.ok) and getattr(job, "status", "") in {
            "completed",
            "partial",
        }
        handoff = None
        if exec_result.ok and getattr(job, "output_stored_path", ""):
            handoff = {
                "stored_path": job.output_stored_path,
                "filename": getattr(job, "output_filename", "") or "pipe_output",
            }
        return {
            "ok": dms_ok,
            "job_id": str(job.id),
            "message": exec_result.user_message,
            "error_code": exec_result.error_code or "",
            "handoff": handoff,
            "artifacts": [
                {"role": "output", "path": getattr(job, "output_stored_path", "")}
            ],
        }

    return {
        "ok": False,
        "job_id": "",
        "message": MSG_KIND_UNSUPPORTED,
        "error_code": "kind_unsupported",
        "handoff": None,
        "artifacts": [],
    }


def start_run(
    user,
    pipeline: PipelineDefinition,
    uploaded_file,
    *,
    dry_run: bool,
    request=None,
) -> OperationResult:
    blocked = run_gate_reason(pipeline, user)
    if blocked:
        code = "forbidden" if blocked == MSG_NO_RUN else "validation_form"
        return OperationResult.failure(code, blocked)

    version = pipeline.current_version
    steps = list(version.steps or [])
    if not steps:
        return OperationResult.failure("validation_form", MSG_NO_VERSION)

    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            MSG_NO_FILE,
            errors={"file": [MSG_NO_FILE]},
        )
    name = getattr(uploaded_file, "name", "") or "file"
    size = getattr(uploaded_file, "size", None)
    if size == 0:
        return OperationResult.failure(
            "validation_form",
            MSG_EMPTY,
            errors={"file": [MSG_EMPTY]},
        )

    for spec in steps:
        slug = str(spec.get("project_slug") or "")
        project = ProjectModel.objects.filter(
            company=pipeline.company, slug=slug, is_archived=False
        ).first()
        if project is None or not _project_can_execute(user, project):
            return OperationResult.failure("forbidden", MSG_NO_STEP_PERM)

    digest = _sha256_upload(uploaded_file)
    now = timezone.now()
    ip = ""
    ua = ""
    if request is not None:
        ip = str(request.META.get("REMOTE_ADDR") or "")[:45]
        ua = str(request.META.get("HTTP_USER_AGENT") or "")[:300]
    run = PipelineRun.objects.create(
        pipeline=pipeline,
        version=version,
        trigger_source=PipelineRun.TRIGGER_UI,
        status=PipelineRun.STATUS_RUNNING,
        dry_run=bool(dry_run),
        input_filename=name[:255],
        input_sha256=digest,
        triggered_by=user,
        started_at=now,
        correlation_id=uuid.uuid4().hex,
        client_ip=ip,
        user_agent=ua,
    )
    step_rows = []
    for spec in steps:
        step_rows.append(
            PipelineStepRun.objects.create(
                run=run,
                order=int(spec.get("order") or 0),
                kind=str(spec.get("kind") or ""),
                label=str(spec.get("label") or spec.get("kind") or ""),
                project_slug=str(spec.get("project_slug") or ""),
                status=PipelineStepRun.STATUS_PENDING,
            )
        )

    current_upload = uploaded_file
    failed = False
    t0 = time.perf_counter()
    try:
        for row in step_rows:
            if failed:
                row.status = PipelineStepRun.STATUS_SKIPPED
                row.skip_reason = "stop_on_error"
                row.save(update_fields=["status", "skip_reason"])
                continue
            project = ProjectModel.objects.filter(
                company=pipeline.company, slug=row.project_slug
            ).first()
            row.status = PipelineStepRun.STATUS_RUNNING
            row.started_at = timezone.now()
            row.save(update_fields=["status", "started_at"])
            step_t0 = time.perf_counter()
            outcome = _invoke_step(
                user, row.kind, project, current_upload, dry_run=bool(dry_run)
            )
            elapsed = int((time.perf_counter() - step_t0) * 1000)
            row.duration_ms = elapsed
            row.finished_at = timezone.now()
            row.app_job_id = outcome.get("job_id") or ""
            row.artifacts = outcome.get("artifacts") or []
            row.user_message = (outcome.get("message") or "")[:500]
            row.error_code = (outcome.get("error_code") or "")[:80]
            if outcome.get("ok"):
                row.status = PipelineStepRun.STATUS_COMPLETED
                handoff = outcome.get("handoff")
                if handoff and handoff.get("stored_path"):
                    current_upload = _wrap_stored(
                        handoff["stored_path"], handoff.get("filename") or "file"
                    )
            else:
                row.status = PipelineStepRun.STATUS_FAILED
                failed = True
                run.failed_step_order = row.order
                run.error_message = (outcome.get("message") or MSG_FAIL)[:500]
            row.save()
    except Exception:
        logger.exception("pipeline_run unexpected run=%s", run.id)
        failed = True
        run.error_message = (
            "Ocurrió un error al ejecutar. Si persiste, contacte al administrador."
        )[:500]

    run.finished_at = timezone.now()
    run.duration_ms = int((time.perf_counter() - t0) * 1000)
    run.status = PipelineRun.STATUS_FAILED if failed else PipelineRun.STATUS_COMPLETED
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "failed_step_order",
            "error_message",
        ]
    )
    pipeline.save(update_fields=["updated_at"])
    message = MSG_FAIL if failed else MSG_OK
    result_cls = OperationResult.failure if failed else OperationResult.success
    if failed:
        return OperationResult.failure(
            "run_failed",
            run.error_message or message,
            run=run,
            run_id=str(run.id),
        )
    return OperationResult.success(
        user_message=message,
        payload={"run": run, "run_id": str(run.id)},
    )


def step_view_rows(run: PipelineRun, *, show_job_links: bool = True) -> list[dict[str, Any]]:
    rows = []
    for step in run.steps.all():
        node = "is-ok"
        if step.status == PipelineStepRun.STATUS_FAILED:
            node = "is-fail"
        elif step.status == PipelineStepRun.STATUS_SKIPPED:
            node = "is-skip"
        job_url = ""
        if show_job_links and step.app_job_id:
            job_url = _job_url(step.kind, step.project_slug, step.app_job_id)
        rows.append(
            {
                "step": step,
                "node_class": node,
                "job_url": job_url,
                "duration_label": (
                    f"{(step.duration_ms or 0) / 1000:.1f}s"
                    if step.duration_ms is not None
                    else "—"
                ),
            }
        )
    return rows
