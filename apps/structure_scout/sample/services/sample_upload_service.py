"""Upload / preview / delete de muestras STRUCTURE SCOUT (sample_upload.md)."""

from __future__ import annotations

import logging
import uuid

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.constants import PREVIEW_LINE_LIMIT, SAMPLE_MAX_BYTES
from apps.dms.file_intake.models import DmsSampleFile
from apps.dms.file_intake.services import detection_service, storage_service
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

# Whitelist MVP Scout (sample_upload.md SU-W1) — no depende de SourceProfile del proyecto.
SCOUT_ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".txt", ".tsv"]

MSG_UPLOAD_OK = "Muestra subida correctamente."
MSG_DELETE_OK = "Muestra eliminada."
MSG_NO_UPLOAD_PERM = "No tiene permiso para subir muestras en este proyecto."
MSG_NO_DELETE_PERM = "No tiene permiso para eliminar muestras en este proyecto."
MSG_NO_PREVIEW_PERM = "No tiene permiso para ver el preview de la muestra."
MSG_NOT_FOUND = "Archivo muestra no encontrado."
MSG_BAD_TYPE = "Tipo de archivo no permitido. Use CSV, Excel o TXT."
MSG_EMPTY = "El archivo está vacío."
MSG_TOO_BIG = "El archivo supera el límite de 10 MB para muestras."


def user_can_upload_sample(user, project: Project) -> bool:
    """PA / ED / GE (SU3)."""
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def user_can_view_preview(user, project: Project) -> bool:
    """CO no ve filas de preview en MVP (SU3)."""
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role != ProjectMembership.ROLE_CO


def accept_attr() -> str:
    return ",".join(SCOUT_ALLOWED_EXTENSIONS)


def list_samples(project: Project, *, limit: int = 20) -> list[dict]:
    samples = list(
        DmsSampleFile.objects.filter(project=project)
        .select_related("uploaded_by")
        .order_by("-created_at")[:limit]
    )
    rows = []
    for index, item in enumerate(samples):
        rows.append(
            {
                "id": str(item.id),
                "original_filename": item.original_filename,
                "size_bytes": item.size_bytes,
                "size_label": detection_service.human_size(item.size_bytes),
                "content_hash": item.content_hash or "",
                "content_hash_short": (item.content_hash or "")[:8],
                "suggestions": item.suggestions or {},
                "created_at": item.created_at,
                "uploaded_by": item.uploaded_by.username if item.uploaded_by_id else "—",
                "is_active": index == 0,
            }
        )
    return rows


def latest_sample(project: Project) -> DmsSampleFile | None:
    return (
        DmsSampleFile.objects.filter(project=project)
        .order_by("-created_at")
        .first()
    )


def get_hub_context(user, project: Project) -> dict:
    membership = project_service.get_membership(user, project)
    samples = list_samples(project)
    active = samples[0] if samples else None
    can_upload = user_can_upload_sample(user, project)
    can_preview = user_can_view_preview(user, project)
    return {
        "samples": samples,
        "samples_count": len(samples),
        "active_sample": active,
        "accept_attr": accept_attr(),
        "allowed_extensions": list(SCOUT_ALLOWED_EXTENSIONS),
        "sample_max_bytes": SAMPLE_MAX_BYTES,
        "sample_max_label": detection_service.human_size(SAMPLE_MAX_BYTES),
        "can_upload_sample": can_upload,
        "can_view_preview": can_preview,
        "membership": membership,
    }


def _validate_upload_file(uploaded_file) -> OperationResult | None:
    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            "Seleccione un archivo para subir.",
            errors={"file": ["Seleccione un archivo."]},
        )
    name = getattr(uploaded_file, "name", "") or ""
    ext = detection_service.extension_of(name)
    if not ext or ext not in SCOUT_ALLOWED_EXTENSIONS:
        return OperationResult.failure(
            "validation_form",
            MSG_BAD_TYPE,
            errors={"file": [MSG_BAD_TYPE]},
        )
    size = getattr(uploaded_file, "size", None)
    if size is not None and size == 0:
        return OperationResult.failure(
            "validation_form",
            MSG_EMPTY,
            errors={"file": [MSG_EMPTY]},
        )
    if size is not None and size > SAMPLE_MAX_BYTES:
        return OperationResult.failure(
            "validation_form",
            MSG_TOO_BIG,
            errors={"file": [MSG_TOO_BIG]},
        )
    return None


@transaction.atomic
def upload_sample(user, project: Project, uploaded_file) -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo Explorador de estructura.",
        )
    if not user_can_upload_sample(user, project):
        return OperationResult.failure("forbidden", MSG_NO_UPLOAD_PERM)

    invalid = _validate_upload_file(uploaded_file)
    if invalid:
        return invalid

    sample_id = uuid.uuid4()
    dest = storage_service.sample_dir(project.company_id, project.id, sample_id)

    try:
        stored_path, size_bytes, content_hash = storage_service.store_upload(
            uploaded_file, dest, prefix_uuid=str(sample_id)
        )
    except Exception:
        logger.exception("scout upload_sample store failed project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al subir la muestra. Si persiste, contacte al administrador.",
        )

    if size_bytes == 0:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            MSG_EMPTY,
            errors={"file": [MSG_EMPTY]},
        )
    if size_bytes > SAMPLE_MAX_BYTES:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            MSG_TOO_BIG,
            errors={"file": [MSG_TOO_BIG]},
        )

    suggestions = detection_service.build_suggestions(
        getattr(uploaded_file, "name", ""), stored_path
    )
    preview = detection_service.preview_rows(
        stored_path,
        filename=getattr(uploaded_file, "name", ""),
        limit=PREVIEW_LINE_LIMIT,
    )

    # version=None: Scout no necesita DmsMappingVersion + target/mapping (SU10 / M2).
    sample = DmsSampleFile.objects.create(
        id=sample_id,
        project=project,
        version=None,
        original_filename=storage_service.sanitize_filename(
            getattr(uploaded_file, "name", "file")
        ),
        stored_path=stored_path,
        size_bytes=size_bytes,
        content_hash=content_hash,
        mime_type=getattr(uploaded_file, "content_type", "") or "",
        uploaded_by=user,
        suggestions=suggestions,
    )
    project.save(update_fields=["updated_at"])

    return OperationResult.success(
        user_message=MSG_UPLOAD_OK,
        payload={
            "sample": sample,
            "stored_file_id": str(sample.id),
            "original_filename": sample.original_filename,
            "size_bytes": sample.size_bytes,
            "size_label": detection_service.human_size(sample.size_bytes),
            "suggestions": suggestions,
            "preview_rows": preview,
        },
    )


def get_sample_preview(user, project: Project, sample_id) -> OperationResult:
    if not project_service.get_membership(user, project):
        return OperationResult.failure("forbidden", "No tiene acceso a este proyecto Explorador.")
    if not user_can_view_preview(user, project):
        return OperationResult.failure("forbidden", MSG_NO_PREVIEW_PERM)
    sample = DmsSampleFile.objects.filter(project=project, id=sample_id).first()
    if sample is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    preview = detection_service.preview_rows(
        sample.stored_path, filename=sample.original_filename
    )
    return OperationResult.success(
        payload={
            "sample": sample,
            "preview_rows": preview,
            "suggestions": sample.suggestions or {},
        }
    )


@transaction.atomic
def delete_sample(user, project: Project, sample_id) -> OperationResult:
    if not user_can_upload_sample(user, project):
        return OperationResult.failure("forbidden", MSG_NO_DELETE_PERM)
    sample = DmsSampleFile.objects.filter(project=project, id=sample_id).first()
    if sample is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    stored = sample.stored_path
    sample.delete()
    try:
        storage_service.delete_stored(stored)
    except Exception:
        logger.exception("scout delete_sample storage project=%s", project.slug)
    project.save(update_fields=["updated_at"])
    return OperationResult.success(user_message=MSG_DELETE_OK)
