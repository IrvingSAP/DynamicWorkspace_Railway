"""M3: destino Job/pipeline + origen de entrada (sin disparar)."""

from __future__ import annotations

from apps.accounts.models import UserProfile
from apps.dms.mapping.models import DmsProjectConfig
from apps.file_pipeline.models import PipelineDefinition
from apps.projects.models import Project, ProjectMembership

from apps.file_scheduler.services import schedule_errors as err

HELP = " Consulte la Ayuda para completar la información correctamente."

MODE_JOB = "job"
MODE_PIPELINE = "pipeline"
ORIGIN_WATCH = "watch"
ORIGIN_ARTIFACT = "artifact"
ORIGIN_NONE = "none"

JOB_KINDS = [
    {"kind": "file_gate", "label": "File Gate", "project_kind": Project.KIND_FILE_GATE},
    {"kind": "dms", "label": "File Pipe", "project_kind": Project.KIND_DMS},
    {"kind": "file_clean", "label": "File Clean", "project_kind": Project.KIND_FILE_CLEAN},
    {"kind": "file_match", "label": "File Match", "project_kind": Project.KIND_FILE_MATCH},
    {"kind": "reverse", "label": "Reverse Studio", "project_kind": Project.KIND_REVERSE},
    {"kind": "structure_scout", "label": "Structure Scout", "project_kind": Project.KIND_STRUCTURE_SCOUT},
    {"kind": "file_split", "label": "File Split", "project_kind": Project.KIND_FILE_SPLIT_MERGE},
    {"kind": "file_merge", "label": "File Merge", "project_kind": Project.KIND_FILE_SPLIT_MERGE},
]
KIND_TO_PROJECT = {row["kind"]: row["project_kind"] for row in JOB_KINDS}
FILE_JOB_KINDS = {row["kind"] for row in JOB_KINDS}

MSG_TARGET_SAVED = err.MSG_TARGET_SAVED
MSG_NO_PUBLISHED = err.MSG_NO_PUBLISHED
MSG_MISSING_JOB_NONE = err.MSG_MISSING_INPUT
MSG_MISSING_WATCH = "Indique el código de la bandeja (File Watch)." + HELP
MSG_MISSING_ARTIFACT = "Indique el hash SHA-256 del artifact." + HELP
MSG_MISSING_NONE_CONFIRM = (
    "Para «Sin archivo» confirme que el pipeline no exige upload en el tick." + HELP
)
MSG_NEED_PROJECT = "Elija un proyecto con versión publicada." + HELP
MSG_NEED_PIPELINE = "Elija un pipeline activo con versión publicada." + HELP
MSG_FORBIDDEN_SAVE = "No tiene permiso para editar el destino de este plan."
MSG_FORBIDDEN_RUN = "No tiene permiso para ejecutar el destino elegido." + HELP


def kind_spec(kind: str) -> dict | None:
    for row in JOB_KINDS:
        if row["kind"] == kind:
            return row
    return None


def published_version_number(project: Project) -> int | None:
    config = getattr(project, "dms_config", None)
    if config is None or not config.current_version_id:
        return None
    version = config.current_version
    return getattr(version, "version_number", None)


def list_projects_for_kind(company, kind: str) -> list[dict]:
    spec = kind_spec(kind)
    if spec is None:
        return []
    qs = (
        Project.objects.filter(
            company=company,
            project_kind=spec["project_kind"],
            is_archived=False,
        )
        .select_related("dms_config", "dms_config__current_version")
        .order_by("slug")
    )
    rows = []
    for project in qs:
        number = published_version_number(project)
        published = number is not None
        label = f"{project.slug} · {project.name}"
        if published:
            label = f"{label} · publicada v{number}"
        else:
            label = f"{label} · sin versión publicada"
        rows.append(
            {
                "id": str(project.id),
                "slug": project.slug,
                "label": label,
                "published": published,
                "version_number": number,
            }
        )
    return rows


def list_pipelines(company) -> list[dict]:
    qs = (
        PipelineDefinition.objects.filter(company=company)
        .select_related("current_version")
        .order_by("slug")
    )
    rows = []
    for pipeline in qs:
        published = pipeline.current_version_id is not None
        active = pipeline.status == PipelineDefinition.STATUS_ACTIVE
        version = pipeline.current_version
        vlabel = f"v{version.version_number}" if version is not None else "sin publicada"
        status = pipeline.get_status_display()
        rows.append(
            {
                "id": str(pipeline.id),
                "slug": pipeline.slug,
                "label": f"{pipeline.slug} · {status} · {vlabel}",
                "published": published,
                "active": active,
                "eligible": published and active,
                "version_number": version.version_number if version else None,
            }
        )
    return rows


def snapshot_from_schedule(schedule) -> dict:
    return {
        "target_mode": schedule.target_mode or MODE_JOB,
        "kind": schedule.target_kind or "file_gate",
        "project_id": str(schedule.target_project_id) if schedule.target_project_id else "",
        "pipeline_id": str(schedule.target_pipeline_id) if schedule.target_pipeline_id else "",
        "input_origin": schedule.input_origin or ORIGIN_WATCH,
        "watch_id": schedule.watch_id or "",
        "artifact_ref": schedule.artifact_ref or "",
        "pipeline_inputs_resolved": "1" if schedule.pipeline_inputs_resolved else "",
    }


def posted_from_request(post) -> dict:
    return {
        "target_mode": (post.get("target_mode") or "").strip(),
        "kind": (post.get("kind") or "").strip(),
        "project_id": (post.get("project_id") or "").strip(),
        "pipeline_id": (post.get("pipeline_id") or "").strip(),
        "input_origin": (post.get("input_origin") or "").strip(),
        "watch_id": (post.get("watch_id") or "").strip(),
        "artifact_ref": (post.get("artifact_ref") or "").strip(),
        "pipeline_inputs_resolved": (post.get("pipeline_inputs_resolved") or "").strip(),
    }


def user_is_company_us(user) -> bool:
    try:
        profile = user.profile
    except Exception:
        return False
    return profile.user_type == UserProfile.USER_SYSTEM


def _can_execute_project(user, project: Project) -> bool:
    if user_is_company_us(user) and project.company_id == user.profile.company_id:
        return True
    membership = ProjectMembership.objects.filter(
        project=project, user=user, is_active=True
    ).first()
    if membership is None:
        return False
    return ProjectMembership.role_can_execute(membership.role)


def actor_can_run_target(user, *, project=None, pipeline=None) -> bool:
    if project is not None:
        return _can_execute_project(user, project)
    if pipeline is None:
        return False
    if user_is_company_us(user) and pipeline.company_id == user.profile.company_id:
        return True
    version = pipeline.current_version
    steps = (version.steps if version is not None else None) or pipeline.draft_steps or []
    if not steps:
        return True
    for step in steps:
        slug = str(step.get("project_slug") or "").strip().lower()
        if not slug:
            continue
        try:
            step_project = Project.objects.get(company=pipeline.company, slug=slug)
        except Project.DoesNotExist:
            return False
        if not _can_execute_project(user, step_project):
            return False
    return True
