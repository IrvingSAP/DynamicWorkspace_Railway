"""Contexto UI Transform execution."""

from django.urls import reverse

from apps.dms.file_intake.services import detection_service, file_intake_persistence_service
from apps.dms.mapping.models import DmsProjectConfig
from apps.dms.source_profile.services import version_publish_service
from apps.dms.transform_execution.services import execution_service
from apps.file_gate.bridge.services import dms_bridge_service


def get_hub_context(
    project,
    membership,
    *,
    download_url_namespace: str = "dms",
    download_url_names: dict[str, str] | None = None,
    force_bridge_disabled: bool = False,
) -> dict:
    publish = version_publish_service.get_publish_context(project)
    published = file_intake_persistence_service.get_published_version(project)
    uploaded = execution_service.list_uploaded_jobs(project)
    history = execution_service.list_history(project)

    config = getattr(project, "dms_config", None)
    if config is None:
        config = DmsProjectConfig.objects.filter(project=project).first()
    bridge_enabled = bool(config and config.file_gate_enabled) and not force_bridge_disabled
    gate_slug = ""
    if config and config.file_gate_project_id:
        gate_slug = config.file_gate_project.slug

    uploaded_jobs = []
    for job in uploaded:
        row = {
            "id": str(job.id),
            "original_filename": job.input_original_filename,
            "size_label": detection_service.human_size(job.input_size_bytes),
            "version_number": job.version.version_number if job.version_id else None,
            "created_at": job.created_at,
            "content_hash_short": _hash_short(job.input_content_hash),
            "bridge": None,
        }
        if bridge_enabled:
            check = dms_bridge_service.precheck_job(project, job)
            if check.ok and not (check.payload or {}).get("skipped"):
                row["bridge"] = {
                    "ok": True,
                    "status_label": check.payload.get("gate_status_label"),
                    "gate_status": check.payload.get("gate_status"),
                    "links": check.payload.get("links") or {},
                    "warning": check.payload.get("file_type_warning") or "",
                }
            elif check.ok:
                row["bridge"] = {"ok": True, "skipped": True}
            else:
                row["bridge"] = {
                    "ok": False,
                    "error_code": check.error_code,
                    "message": check.user_message,
                    "links": (check.payload or {}).get("links") or {},
                    "gate_status": (check.payload or {}).get("gate_status"),
                }
        uploaded_jobs.append(row)

    return {
        "version_publish": publish,
        "has_published_version": published is not None,
        "published_version_number": published.version_number if published else None,
        "bridge_enabled": bridge_enabled,
        "bridge_gate_slug": gate_slug,
        "bridge_settings_url": reverse(
            "dms:file_gate_bridge_settings",
            kwargs={"project_slug": project.slug},
        ),
        "uploaded_jobs": uploaded_jobs,
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
                "file_gate_check": (job.input_suggestions or {}).get("file_gate_check"),
                "downloads": (
                    execution_service.build_download_links(
                        project.slug,
                        job,
                        url_namespace=download_url_namespace,
                        url_names=download_url_names,
                    )
                    if job.status
                    in {"completed", "partial"}
                    and not execution_service.is_download_expired(job)
                    else {}
                ),
            }
            for job in history
        ],
    }


def _hash_short(value: str) -> str:
    value = value or ""
    if len(value) < 8:
        return value or "—"
    return f"{value[:4]}…{value[-2:]}"
