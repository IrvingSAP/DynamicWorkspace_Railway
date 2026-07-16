"""Contexto UI Transform execution."""

from apps.dms.file_intake.services import detection_service, file_intake_persistence_service
from apps.dms.source_profile.services import version_publish_service
from apps.dms.transform_execution.services import execution_service


def get_hub_context(project, membership) -> dict:
    publish = version_publish_service.get_publish_context(project)
    published = file_intake_persistence_service.get_published_version(project)
    uploaded = execution_service.list_uploaded_jobs(project)
    history = execution_service.list_history(project)

    return {
        "version_publish": publish,
        "has_published_version": published is not None,
        "published_version_number": published.version_number if published else None,
        "uploaded_jobs": [
            {
                "id": str(job.id),
                "original_filename": job.input_original_filename,
                "size_label": detection_service.human_size(job.input_size_bytes),
                "version_number": job.version.version_number if job.version_id else None,
                "created_at": job.created_at,
            }
            for job in uploaded
        ],
        "history_jobs": [
            {
                "id": str(job.id),
                "status": job.status,
                "finished_at": job.finished_at,
                "executed_by": (
                    job.executed_by.get_username() if job.executed_by_id else "—"
                ),
                "version_number": job.version.version_number if job.version_id else None,
                "input_filename": job.input_original_filename,
                "output_filename": job.output_filename,
                "rows_ok": job.rows_ok,
                "rows_rejected": job.rows_rejected,
                "expired": execution_service.is_download_expired(job),
                "downloads": (
                    execution_service.build_download_links(project.slug, job)
                    if job.status
                    in {"completed", "partial"}
                    and not execution_service.is_download_expired(job)
                    else {}
                ),
            }
            for job in history
        ],
    }
