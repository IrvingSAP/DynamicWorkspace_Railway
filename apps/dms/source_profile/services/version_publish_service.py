"""Publicación de versiones DmsMappingVersion (project_lifecycle.md)."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.field_mapping.models import DmsFieldMappingSet
from apps.dms.field_mapping.services import field_mapping_persistence_service
from apps.dms.mapping.models import DmsProjectConfig
from apps.dms.source_profile.models import DmsMappingVersion, DmsSourceProfile
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.target_profile.models import DmsTargetProfile
from apps.dms.target_profile.services import target_persistence_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)


def get_publish_context(project: Project) -> dict:
    draft = source_persistence_service.get_draft_version(project)
    target_persistence_service.ensure_target_on_version(draft)
    field_mapping_persistence_service.ensure_mapping_set_on_version(draft)
    config = getattr(project, "dms_config", None)
    published = None
    if config is not None and config.current_version_id:
        published = config.current_version

    return {
        "draft_version_number": draft.version_number,
        "draft_version_id": str(draft.id),
        "published_version_label": (
            f"v{published.version_number} publicada" if published else "Sin versión publicada"
        ),
        "published_version_number": published.version_number if published else None,
        "published_at": published.published_at if published else None,
        "has_published_version": published is not None,
    }


@transaction.atomic
def publish_draft_version(user, project: Project) -> OperationResult:
    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para publicar versiones de este proyecto.",
        )

    draft = (
        DmsMappingVersion.objects.select_for_update()
        .filter(
            project=project,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        .select_related("source_profile", "target_profile", "field_mapping_set")
        .order_by("-version_number")
        .first()
    )
    if draft is None:
        return OperationResult.failure(
            "not_found",
            "No hay borrador disponible para publicar.",
        )

    try:
        profile = draft.source_profile
    except DmsSourceProfile.DoesNotExist:
        return OperationResult.failure(
            "validation_form",
            "El borrador no tiene perfil de origen.",
        )

    target_persistence_service.ensure_target_on_version(draft)
    try:
        target_profile = draft.target_profile
    except DmsTargetProfile.DoesNotExist:
        return OperationResult.failure(
            "validation_form",
            "El borrador no tiene perfil de destino.",
        )

    field_mapping_persistence_service.ensure_mapping_set_on_version(draft)
    mapping_set = draft.field_mapping_set

    source = source_persistence_service.profile_to_dict(profile)
    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list as normalize_source_fields,
    )
    from apps.dms.target_profile.services.field_normalization_service import (
        normalize_fields_list as normalize_target_fields,
    )

    source["fields"] = normalize_source_fields(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    errors, warnings = source_persistence_service.validate_source_dict(source, strict=True)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Complete y corrija el perfil de origen antes de publicar.",
            errors=errors,
            warnings=warnings,
        )

    target = target_persistence_service.profile_to_dict(target_profile)
    target["fields"] = normalize_target_fields(
        target.get("fields") or [], target.get("file_type_code", "")
    )
    target_errors, target_warnings = target_persistence_service.validate_target_dict(
        target, strict=True
    )
    if target_errors:
        return OperationResult.failure(
            "validation_form",
            "Complete y corrija el perfil de destino antes de publicar.",
            errors=target_errors,
            warnings=target_warnings,
        )
    warnings = {**warnings, **target_warnings}

    mappings_data = field_mapping_persistence_service.set_to_dict(mapping_set)
    mapping_errors, mapping_warnings = field_mapping_persistence_service.validate_mappings_dict(
        mappings_data,
        source_fields=source.get("fields") or [],
        target_fields=target.get("fields") or [],
        strict=True,
    )
    if mapping_errors:
        return OperationResult.failure(
            "validation_form",
            "Complete y corrija el mapeo de campos antes de publicar.",
            errors=mapping_errors,
            warnings=mapping_warnings,
        )
    warnings = {**warnings, **mapping_warnings}

    try:
        now = timezone.now()
        draft.status = DmsMappingVersion.STATUS_PUBLISHED
        draft.published_at = now
        draft.published_by = user
        draft.save(update_fields=["status", "published_at", "published_by", "updated_at"])

        config, _created = DmsProjectConfig.objects.select_for_update().get_or_create(
            project=project,
        )
        config.current_version = draft
        config.save(update_fields=["current_version", "updated_at"])

        next_number = draft.version_number + 1
        new_draft = DmsMappingVersion.objects.create(
            project=project,
            version_number=next_number,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        DmsSourceProfile.objects.create(
            version=new_draft,
            **source_persistence_service.profile_defaults_from_dict(source),
        )
        DmsTargetProfile.objects.create(
            version=new_draft,
            **target_persistence_service.profile_defaults_from_dict(target),
        )
        DmsFieldMappingSet.objects.create(
            version=new_draft,
            **field_mapping_persistence_service.profile_defaults_from_dict(mappings_data),
        )

        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("publish_draft_version unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al publicar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message=(
            f"Versión v{draft.version_number} publicada correctamente. "
            f"Nuevo borrador v{next_number} listo para edición."
        ),
        payload={
            "published_version": draft,
            "new_draft_version": new_draft,
            "published_version_number": draft.version_number,
            "new_draft_version_number": next_number,
            "warnings": warnings,
            "warning_messages": source_persistence_service.flatten_validation_messages(warnings),
        },
    )
