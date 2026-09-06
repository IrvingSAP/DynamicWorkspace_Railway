"""M6: disparo por dependencia (tras Job/pipeline padre)."""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.dms.file_intake.models import DmsExecutionJob
from apps.file_pipeline.models import PipelineRun
from apps.file_scheduler.models import Schedule
from apps.file_scheduler.services import schedule_errors as err
from apps.file_scheduler.services import schedule_target as target_svc
from apps.projects.models import Project

logger = logging.getLogger(__name__)

HELP = " Consulte la Ayuda para completar la información correctamente."
MSG_SAVED = err.MSG_TRIGGER_SAVED
MSG_FORBIDDEN = "No tiene permiso para editar la dependencia de este plan."
MSG_NEED_PARENT = "Elija el Job o pipeline padre." + HELP
MSG_CYCLE = err.MSG_CYCLE
MSG_ACCEPTED_NOT_GATE = "La condición «Aceptado» solo aplica si el padre es File Gate." + HELP
MSG_PAUSED = err.MSG_PAUSED

MODE_TIME = Schedule.TRIGGER_TIME
MODE_DEP = Schedule.TRIGGER_DEPENDENCY
ON_OK = {Schedule.ON_SUCCEEDED, Schedule.ON_ACCEPTED, Schedule.ON_COMPLETED}

JOB_TERMINAL_OK = {DmsExecutionJob.STATUS_COMPLETED}
JOB_TERMINAL_ANY = {
    DmsExecutionJob.STATUS_COMPLETED,
    DmsExecutionJob.STATUS_PARTIAL,
    DmsExecutionJob.STATUS_FAILED,
}
PIPE_OK = {PipelineRun.STATUS_COMPLETED}
PIPE_ANY = {PipelineRun.STATUS_COMPLETED, PipelineRun.STATUS_FAILED}


def list_parent_projects(company) -> list[dict]:
    rows = []
    seen = set()
    for kind_row in target_svc.JOB_KINDS:
        for item in target_svc.list_projects_for_kind(company, kind_row["kind"]):
            if not item["published"] or item["id"] in seen:
                continue
            seen.add(item["id"])
            label = f"{kind_row['label']} · {item['label']}"
            rows.append({**item, "kind": kind_row["kind"], "label": label})
    rows.sort(key=lambda r: r["slug"])
    return rows


def snapshot_from_schedule(schedule: Schedule) -> dict:
    return {
        "trigger_mode": schedule.trigger_mode or MODE_TIME,
        "parent_kind": schedule.parent_kind or Schedule.PARENT_JOB,
        "parent_project_id": str(schedule.parent_project_id)
        if schedule.parent_project_id
        else "",
        "parent_pipeline_id": str(schedule.parent_pipeline_id)
        if schedule.parent_pipeline_id
        else "",
        "on_parent": schedule.on_parent or Schedule.ON_SUCCEEDED,
    }


def posted_from_request(post) -> dict:
    return {
        "trigger_mode": (post.get("trigger_mode") or "").strip(),
        "parent_kind": (post.get("parent_kind") or "").strip(),
        "parent_project_id": (post.get("parent_project_id") or "").strip(),
        "parent_pipeline_id": (post.get("parent_pipeline_id") or "").strip(),
        "on_parent": (post.get("on_parent") or "").strip(),
    }


def parent_condition_met(*, schedule: Schedule, job=None, pipeline_run=None) -> bool:
    rule = schedule.on_parent or Schedule.ON_SUCCEEDED
    if job is not None:
        if rule == Schedule.ON_ACCEPTED:
            return _gate_accepted(job)
        if rule == Schedule.ON_COMPLETED:
            return job.status in JOB_TERMINAL_ANY
        return job.status in JOB_TERMINAL_OK
    if pipeline_run is not None:
        if rule == Schedule.ON_ACCEPTED:
            return False
        if rule == Schedule.ON_COMPLETED:
            return pipeline_run.status in PIPE_ANY
        return pipeline_run.status in PIPE_OK
    return False


def _gate_accepted(job) -> bool:
    project = getattr(job, "project", None)
    if project is None or getattr(project, "project_kind", "") != Project.KIND_FILE_GATE:
        return False
    if job.status != DmsExecutionJob.STATUS_COMPLETED:
        return False
    suggestions = getattr(job, "input_suggestions", None) or {}
    gate = suggestions.get("gate_result") or {}
    status = str(gate.get("status") or "").lower()
    verdict = str(gate.get("verdict") or "").lower()
    if verdict == "accepted":
        return True
    return status in {"passed", "passed_with_warnings", "accepted"}


def matching_schedules_for_job(job: DmsExecutionJob):
    return (
        Schedule.objects.filter(
            trigger_mode=MODE_DEP,
            parent_kind=Schedule.PARENT_JOB,
            parent_project_id=job.project_id,
            status=Schedule.STATUS_ACTIVE,
            company_id=job.project.company_id,
            company__is_active=True,
        )
        .select_related(
            "company",
            "target_project",
            "target_project__dms_config",
            "target_project__dms_config__current_version",
            "target_pipeline",
            "target_pipeline__current_version",
            "parent_project",
        )
    )


def matching_schedules_for_pipeline_run(run: PipelineRun):
    return (
        Schedule.objects.filter(
            trigger_mode=MODE_DEP,
            parent_kind=Schedule.PARENT_PIPELINE,
            parent_pipeline_id=run.pipeline_id,
            status=Schedule.STATUS_ACTIVE,
            company_id=run.pipeline.company_id,
            company__is_active=True,
        )
        .select_related(
            "company",
            "target_project",
            "target_project__dms_config",
            "target_project__dms_config__current_version",
            "target_pipeline",
            "target_pipeline__current_version",
            "parent_pipeline",
        )
    )


def notify_job_finished(job: DmsExecutionJob) -> int:
    from apps.file_scheduler.services.schedule_tick import fire_from_parent

    if job.status == DmsExecutionJob.STATUS_CANCELLED:
        return 0
    n = 0
    now = job.finished_at or timezone.now()
    for schedule in matching_schedules_for_job(job):
        if not parent_condition_met(schedule=schedule, job=job):
            continue
        tick = fire_from_parent(
            schedule,
            now=now,
            parent_job_id=str(job.id),
        )
        if tick:
            n += 1
    return n


def notify_pipeline_finished(run: PipelineRun) -> int:
    from apps.file_scheduler.services.schedule_tick import fire_from_parent

    if run.status == PipelineRun.STATUS_CANCELLED:
        return 0
    n = 0
    now = run.finished_at or timezone.now()
    for schedule in matching_schedules_for_pipeline_run(run):
        if not parent_condition_met(schedule=schedule, pipeline_run=run):
            continue
        tick = fire_from_parent(
            schedule,
            now=now,
            parent_pipeline_run_id=str(run.id),
        )
        if tick:
            n += 1
    return n
