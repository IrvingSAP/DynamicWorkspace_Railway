"""Contexto UI File intake (file_intake.md)."""

from dataclasses import dataclass

from apps.dms.file_intake.constants import PRODUCTION_FULL_MAX_BYTES, SAMPLE_MAX_BYTES
from apps.dms.file_intake.models import DmsExecutionJob, DmsSampleFile
from apps.dms.file_intake.services import detection_service, file_intake_persistence_service
from apps.dms.source_profile.services import version_publish_service


@dataclass
class IntakeHubContext:
    project_name: str
    project_slug: str
    membership_role: str
    draft_version_label: str
    published_version_label: str
    has_published_version: bool
    samples_count: int
    jobs_uploaded_count: int
    accept_attr: str
    sample_max_label: str
    production_max_label: str


def get_hub_context(project, membership) -> dict:
    publish = version_publish_service.get_publish_context(project)
    samples = list(
        DmsSampleFile.objects.filter(project=project).order_by("-created_at")[:20]
    )
    jobs = list(
        DmsExecutionJob.objects.filter(project=project)
        .select_related("version")
        .order_by("-created_at")[:20]
    )
    exts = detection_service.allowed_extensions_for_project(project)
    accept = ",".join(exts)
    role = membership.role if membership else "—"

    sample_rows = [
        {
            "id": str(item.id),
            "original_filename": item.original_filename,
            "size_label": detection_service.human_size(item.size_bytes),
            "suggestions": item.suggestions or {},
            "created_at": item.created_at,
        }
        for item in samples
    ]
    job_rows = [
        {
            "id": str(item.id),
            "original_filename": item.input_original_filename,
            "size_label": detection_service.human_size(item.input_size_bytes),
            "status": item.status,
            "version_number": item.version.version_number if item.version_id else None,
            "created_at": item.created_at,
        }
        for item in jobs
    ]

    return {
        "samples": sample_rows,
        "jobs": job_rows,
        "allowed_extensions": exts,
        "accept_attr": accept,
        "sample_max_bytes": SAMPLE_MAX_BYTES,
        "production_max_bytes": PRODUCTION_FULL_MAX_BYTES,
        "can_upload_sample": False,  # filled by view
        "can_upload_production": False,
        "hub": IntakeHubContext(
            project_name=project.name,
            project_slug=project.slug,
            membership_role=role,
            draft_version_label=f"Borrador v{publish['draft_version_number']}",
            published_version_label=publish["published_version_label"],
            has_published_version=publish["has_published_version"],
            samples_count=len(sample_rows),
            jobs_uploaded_count=sum(
                1 for job in jobs if job.status == DmsExecutionJob.STATUS_UPLOADED
            ),
            accept_attr=accept,
            sample_max_label=detection_service.human_size(SAMPLE_MAX_BYTES),
            production_max_label=detection_service.human_size(PRODUCTION_FULL_MAX_BYTES),
        ),
        "version_publish": publish,
        "published_version": file_intake_persistence_service.get_published_version(project),
    }
