"""Persistencia SampleFile y upload de producción (file_intake.md)."""

from __future__ import annotations

import logging
import uuid

from django.db import transaction

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.constants import (
    PREVIEW_LINE_LIMIT,
    PRODUCTION_FULL_MAX_BYTES,
    SAMPLE_MAX_BYTES,
)
from apps.dms.file_intake.models import DmsExecutionJob, DmsSampleFile
from apps.dms.file_intake.services import detection_service, storage_service
from apps.dms.mapping.models import DmsProjectConfig
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

logger = logging.getLogger(__name__)


def user_can_upload_sample(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def user_can_upload_production(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def _validate_upload_file(uploaded_file, *, allowed_exts: list[str], max_bytes: int) -> OperationResult | None:
    if uploaded_file is None:
        return OperationResult.failure(
            "validation_form",
            "Seleccione un archivo para subir.",
            errors={"file": ["Seleccione un archivo."]},
        )
    name = getattr(uploaded_file, "name", "") or ""
    ext = detection_service.extension_of(name)
    if not ext or ext not in allowed_exts:
        return OperationResult.failure(
            "validation_form",
            "Tipo de archivo no permitido para este proyecto.",
            errors={
                "file": [
                    f"Extensión «{ext or 'sin extensión'}» no permitida. "
                    f"Permitidas: {', '.join(allowed_exts)}"
                ]
            },
        )
    size = getattr(uploaded_file, "size", None)
    if size is not None and size == 0:
        return OperationResult.failure(
            "validation_form",
            "El archivo está vacío.",
            errors={"file": ["El archivo no puede estar vacío."]},
        )
    if size is not None and size > max_bytes:
        return OperationResult.failure(
            "validation_form",
            f"El archivo supera el límite de {detection_service.human_size(max_bytes)}.",
            errors={
                "file": [
                    f"Tamaño máximo permitido: {detection_service.human_size(max_bytes)}."
                ]
            },
        )
    return None



@transaction.atomic
def upload_sample(user, project: Project, uploaded_file) -> OperationResult:
    if not user_can_upload_sample(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para subir archivos muestra.",
        )

    allowed = detection_service.allowed_extensions_for_project(project)
    invalid = _validate_upload_file(
        uploaded_file, allowed_exts=allowed, max_bytes=SAMPLE_MAX_BYTES
    )
    if invalid:
        return invalid

    version = source_persistence_service.get_or_create_draft_version(project)
    sample_id = uuid.uuid4()
    dest = storage_service.sample_dir(project.company_id, project.id, sample_id)

    try:
        stored_path, size_bytes, content_hash = storage_service.store_upload(
            uploaded_file, dest, prefix_uuid=str(sample_id)
        )
    except Exception:
        logger.exception("upload_sample store failed project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    if size_bytes == 0:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            "El archivo está vacío.",
            errors={"file": ["El archivo no puede estar vacío."]},
        )
    if size_bytes > SAMPLE_MAX_BYTES:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            f"El archivo supera el límite de {detection_service.human_size(SAMPLE_MAX_BYTES)}.",
        )

    suggestions = detection_service.build_suggestions(
        getattr(uploaded_file, "name", ""), stored_path
    )
    preview = detection_service.preview_rows(
        stored_path,
        filename=getattr(uploaded_file, "name", ""),
        limit=PREVIEW_LINE_LIMIT,
    )

    sample = DmsSampleFile.objects.create(
        id=sample_id,
        project=project,
        version=version,
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
        user_message="Archivo muestra subido correctamente.",
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
    if not user_can_upload_sample(user, project) and not project_service.get_membership(
        user, project
    ):
        return OperationResult.failure("forbidden", "No tiene acceso a este proyecto DMS.")
    sample = DmsSampleFile.objects.filter(project=project, id=sample_id).first()
    if sample is None:
        return OperationResult.failure("not_found", "Archivo muestra no encontrado.")
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
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para eliminar archivos muestra.",
        )
    sample = DmsSampleFile.objects.filter(project=project, id=sample_id).first()
    if sample is None:
        return OperationResult.failure("not_found", "Archivo muestra no encontrado.")
    stored = sample.stored_path
    sample.delete()
    try:
        storage_service.delete_stored(stored)
    except Exception:
        logger.exception("delete_sample storage project=%s", project.slug)
    return OperationResult.success(user_message="Archivo muestra eliminado correctamente.")


def get_published_version(project: Project) -> DmsMappingVersion | None:
    config = getattr(project, "dms_config", None)
    if config is None:
        config = DmsProjectConfig.objects.filter(project=project).first()
    if config is None or not config.current_version_id:
        return None
    version = config.current_version
    if version is None or version.status != DmsMappingVersion.STATUS_PUBLISHED:
        return None
    return version


@transaction.atomic
def upload_production(user, project: Project, uploaded_file) -> OperationResult:
    if not user_can_upload_production(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para subir archivos de producción.",
        )

    published = get_published_version(project)
    if published is None:
        return OperationResult.failure(
            "validation_form",
            "Publique una versión antes de ejecutar.",
            errors={"version": ["Se requiere una versión publicada."]},
        )

    allowed = detection_service.allowed_extensions_for_project(project)
    # Prefer published source profile extensions
    try:
        profile = published.source_profile
        code = profile.file_type_code
        from apps.dms.models import SourceFileType

        match = SourceFileType.objects.filter(code=code, is_active=True).first()
        if match and match.extensions:
            allowed = [str(ext).lower() for ext in match.extensions]
    except Exception:
        pass

    invalid = _validate_upload_file(
        uploaded_file, allowed_exts=allowed, max_bytes=PRODUCTION_FULL_MAX_BYTES
    )
    if invalid:
        return invalid

    job_id = uuid.uuid4()
    dest = storage_service.job_input_dir(project.company_id, project.id, job_id)
    try:
        stored_path, size_bytes, content_hash = storage_service.store_upload(
            uploaded_file, dest, prefix_uuid=str(job_id)
        )
    except Exception:
        logger.exception("upload_production store failed project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    if size_bytes == 0:
        storage_service.delete_stored(stored_path)
        return OperationResult.failure(
            "validation_form",
            "El archivo está vacío.",
        )

    suggestions = detection_service.build_suggestions(
        getattr(uploaded_file, "name", ""), stored_path
    )
    preview = detection_service.preview_rows(
        stored_path,
        filename=getattr(uploaded_file, "name", ""),
        limit=PREVIEW_LINE_LIMIT,
    )

    job = DmsExecutionJob.objects.create(
        id=job_id,
        project=project,
        version=published,
        job_type=DmsExecutionJob.JOB_FULL,
        status=DmsExecutionJob.STATUS_UPLOADED,
        input_original_filename=storage_service.sanitize_filename(
            getattr(uploaded_file, "name", "file")
        ),
        input_stored_path=stored_path,
        input_size_bytes=size_bytes,
        input_content_hash=content_hash,
        input_mime_type=getattr(uploaded_file, "content_type", "") or "",
        input_suggestions=suggestions,
        executed_by=user,
    )
    project.save(update_fields=["updated_at"])

    return OperationResult.success(
        user_message="Archivo de producción subido correctamente.",
        payload={
            "job": job,
            "job_id": str(job.id),
            "original_filename": job.input_original_filename,
            "size_bytes": job.input_size_bytes,
            "size_label": detection_service.human_size(job.input_size_bytes),
            "suggestions": suggestions,
            "preview_rows": preview,
            "published_version_number": published.version_number,
        },
    )
