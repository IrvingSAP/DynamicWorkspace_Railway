"""Almacenamiento interno DMS bajo MEDIA_ROOT/dms/… (file_intake.md)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.conf import settings


def dms_storage_root() -> Path:
    configured = getattr(settings, "DMS_STORAGE_ROOT", None)
    if configured:
        return Path(configured)
    return Path(settings.MEDIA_ROOT) / "dms"


def sanitize_filename(name: str) -> str:
    base = Path(name or "file").name
    base = base.replace("\\", "_").replace("/", "_")
    if ".." in base:
        base = base.replace("..", "_")
    cleaned = re.sub(r"[^\w.\- ()\[\]]+", "_", base, flags=re.UNICODE).strip(" ._")
    return cleaned[:180] or "file"


def sha256_of_chunks(chunks) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()


def relative_to_media(absolute: Path) -> str:
    media = Path(settings.MEDIA_ROOT).resolve()
    resolved = absolute.resolve()
    try:
        return str(resolved.relative_to(media)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def absolute_from_stored(stored_path: str) -> Path:
    path = Path(stored_path)
    if path.is_absolute():
        return path
    return Path(settings.MEDIA_ROOT) / path


def sample_dir(company_id, project_id, sample_id) -> Path:
    return (
        dms_storage_root()
        / str(company_id)
        / "projects"
        / str(project_id)
        / "samples"
        / str(sample_id)
        / "original"
    )


def job_input_dir(company_id, project_id, job_id) -> Path:
    return (
        dms_storage_root()
        / str(company_id)
        / "projects"
        / str(project_id)
        / "jobs"
        / str(job_id)
        / "input"
    )


def job_output_dir(company_id, project_id, job_id) -> Path:
    return (
        dms_storage_root()
        / str(company_id)
        / "projects"
        / str(project_id)
        / "jobs"
        / str(job_id)
        / "output"
    )


def job_reports_dir(company_id, project_id, job_id) -> Path:
    return (
        dms_storage_root()
        / str(company_id)
        / "projects"
        / str(project_id)
        / "jobs"
        / str(job_id)
        / "reports"
    )


def store_upload(uploaded_file, destination_dir: Path, *, prefix_uuid: str) -> tuple[str, int, str]:
    """
    Guarda el upload en destination_dir.
    Retorna (stored_path relativo a MEDIA_ROOT, size_bytes, sha256).
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(getattr(uploaded_file, "name", "file"))
    final_name = f"{prefix_uuid}_{safe_name}"
    absolute = destination_dir / final_name

    size = 0
    digest = hashlib.sha256()
    with absolute.open("wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
            size += len(chunk)
            digest.update(chunk)

    return relative_to_media(absolute), size, digest.hexdigest()


def delete_stored(stored_path: str) -> None:
    if not stored_path:
        return
    path = absolute_from_stored(stored_path)
    if path.is_file():
        path.unlink(missing_ok=True)
    # Best-effort cleanup of empty parents up to samples/jobs leaf
    parent = path.parent
    for _ in range(3):
        if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        else:
            break
