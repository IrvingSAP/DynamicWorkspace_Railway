"""Publicación del contrato FILE GATE (solo esquema; sin destino ni mapeo)."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.mapping.models import DmsProjectConfig
from apps.dms.source_profile.models import DmsMappingVersion, DmsSourceProfile
from apps.dms.source_profile.services import source_persistence_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)


def get_publish_context(project: Project) -> dict:
    draft = source_persistence_service.get_draft_version(project)
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
def publish_draft_schema(user, project: Project) -> OperationResult:
    if project.project_kind != Project.KIND_FILE_GATE:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE GATE.",
        )

    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para publicar el contrato de este proyecto.",
        )

    draft = (
        DmsMappingVersion.objects.select_for_update()
        .filter(
            project=project,
            status=DmsMappingVersion.STATUS_DRAFT,
        )
        .select_related("source_profile")
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
            "El borrador no tiene contrato de validación.",
        )

    source = source_persistence_service.profile_to_dict(profile)
    from apps.dms.source_profile.services.field_normalization_service import (
        normalize_fields_list as normalize_source_fields,
    )

    source["fields"] = normalize_source_fields(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    errors, warnings = source_persistence_service.validate_source_dict(source, strict=True)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Complete y corrija el contrato antes de publicar.",
            errors=errors,
            warnings=warnings,
        )

    from apps.file_gate.policy.services import gate_policy_service

    policy, policy_errors, policy_warnings = gate_policy_service.ensure_policy_for_publish(
        project
    )
    if policy_errors:
        return OperationResult.failure(
            "validation_form",
            "Complete y corrija la política de validación antes de publicar.",
            errors=policy_errors,
            warnings=policy_warnings,
        )
    warnings = {**warnings, **policy_warnings}

    # Releer tras materializar defaults de política en el borrador.
    source = source_persistence_service.profile_to_dict(profile)
    source["fields"] = normalize_source_fields(
        source.get("fields") or [], source.get("file_type_code", "")
    )
    config = dict(source.get("config") or {})
    config["gate_policy"] = policy
    source["config"] = config
    source_persistence_service.apply_dict_to_profile(profile, source)
    profile.save()

    report = source.get("processing_report") or {}
    if report.get("report_enabled") is False:
        warnings.setdefault("processing_report", []).append(
            "El informe del gate está deshabilitado; se recomienda dejarlo activo."
        )

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

        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("publish_draft_schema unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al publicar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message=(
            f"Contrato v{draft.version_number} publicado correctamente. "
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
