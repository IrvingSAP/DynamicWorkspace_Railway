"""Aplicar StructureDraft a destino STRUCTURE SCOUT M6 (apply_target.md)."""

from __future__ import annotations

import logging

from django.db import transaction
from django.urls import reverse

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service
from apps.structure_scout.draft.services import save_draft_service
from apps.structure_scout.models import ScoutApply, StructureDraft

logger = logging.getLogger(__name__)

MSG_NO_DRAFT = "Guarde un borrador de estructura antes de aplicar a un destino."
MSG_NO_TARGET = "Seleccione un proyecto destino."
MSG_NO_APPLY = "No tiene permiso para aplicar el borrador a un destino."
MSG_TARGET_FORBIDDEN = (
    "No puede aplicar a este destino. Verifique compañía y rol (PA/ED)."
)
MSG_APPLY_OK = (
    "Borrador sembrado en el destino. Abra el proyecto para revisar y publicar allí."
)
MSG_APPLY_FAIL = (
    "No se pudo aplicar el borrador al destino. Si persiste, contacte al administrador."
)

MVP_KINDS = (
    (ScoutApply.KIND_FILE_GATE, "FILE GATE"),
    (ScoutApply.KIND_REVERSE, "Reverse Studio"),
)

KIND_TO_PROJECT = {
    ScoutApply.KIND_FILE_GATE: Project.KIND_FILE_GATE,
    ScoutApply.KIND_REVERSE: Project.KIND_REVERSE,
}


def user_can_apply_from_scout(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def user_can_edit_target(user, target: Project) -> bool:
    return source_persistence_service.user_can_edit_source(user, target)


def has_successful_apply(project: Project) -> bool:
    return ScoutApply.objects.filter(
        project=project, status=ScoutApply.STATUS_OK
    ).exists()


def list_eligible_targets(user, scout_project: Project, target_kind: str) -> list[dict]:
    project_kind = KIND_TO_PROJECT.get(target_kind)
    if not project_kind:
        return []

    qs = (
        Project.objects.filter(
            company_id=scout_project.company_id,
            project_kind=project_kind,
            is_archived=False,
        )
        .order_by("name", "slug")
    )
    results = []
    for item in qs:
        if item.id == scout_project.id:
            continue
        if not user_can_edit_target(user, item):
            continue
        current = source_persistence_service.get_source_dict(item)
        field_count = len(current.get("fields") or [])
        results.append(
            {
                "id": str(item.id),
                "slug": item.slug,
                "name": item.name,
                "field_count": field_count,
                "file_type_code": current.get("file_type_code") or "",
            }
        )
    return results


def _excel_column(index: int) -> str:
    """0-based index → A, B, … Z, AA."""
    n = index
    letters = []
    while True:
        letters.append(chr(ord("A") + (n % 26)))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(letters))


def map_scout_source_to_partials(source: dict) -> tuple[dict, dict]:
    """Build (meta_partial, fields_partial) for two-step save_source."""
    source = source or {}
    file_type = (source.get("file_type_code") or "").strip()
    encoding = (source.get("encoding_code") or "utf-8").strip() or "utf-8"
    line_ending = (source.get("line_ending_code") or "lf").strip() or "lf"
    delimiter = source.get("delimiter")
    if delimiter is None:
        delimiter = ";"
    has_header = bool(source.get("has_header", True))
    header_row = source.get("header_row") if has_header else None
    if has_header and not header_row:
        header_row = 1

    config: dict = {
        "encoding_code": encoding,
        "line_ending_code": line_ending,
        "has_header": has_header,
    }
    if header_row is not None:
        config["header_row"] = header_row
    if file_type in {"csv", "txt_delimited"}:
        config["delimiter"] = delimiter or ";"
        config.setdefault("quote_char", '"')
        config.setdefault("escape_char", "\\")
    elif file_type == "xlsx":
        config.setdefault("sheet_name", "Hoja1")

    meta = {
        "file_type_code": file_type,
        "encoding_code": encoding,
        "line_ending_code": line_ending,
        "config": config,
    }

    fields = []
    for i, raw in enumerate(source.get("fields") or []):
        name = (raw.get("name") or "").strip()
        if not name:
            continue
        item = {
            "name": name,
            "label": (raw.get("label") or name).strip() or name,
            "content_type": (raw.get("content_type") or "").strip(),
            "required": bool(raw.get("required")),
        }
        if file_type in {"csv", "txt_delimited"}:
            item["column_index"] = i
            item["source_column"] = name.upper()
        elif file_type == "xlsx":
            item["column"] = _excel_column(i)
        elif file_type == "txt_fixed":
            item["start"] = 1
            item["end"] = 1
            item["length"] = 1
        fields.append(item)

    return meta, {"fields": fields}


def target_deep_link(target: Project) -> str:
    if target.project_kind == Project.KIND_FILE_GATE:
        return reverse(
            "file_gate:schema_hub", kwargs={"project_slug": target.slug}
        )
    if target.project_kind == Project.KIND_REVERSE:
        return reverse(
            "reverse_studio:input_hub", kwargs={"project_slug": target.slug}
        )
    return reverse("dashboard:home")


def get_hub_context(user, scout_project: Project) -> dict:
    draft = save_draft_service.get_current_draft(scout_project)
    has_draft = draft is not None
    can_apply = user_can_apply_from_scout(user, scout_project)
    source = (draft.payload or {}).get("source") if draft else {}
    fields_count = len((source or {}).get("fields") or [])

    selected_kind = ScoutApply.KIND_FILE_GATE
    targets = (
        list_eligible_targets(user, scout_project, selected_kind) if has_draft else []
    )

    return {
        "draft": draft,
        "has_draft": has_draft,
        "can_apply": can_apply,
        "kind_choices": MVP_KINDS,
        "selected_kind": selected_kind,
        "targets": targets,
        "fields_count": fields_count,
        "source": source or {},
        "status": draft.status if draft else "",
        "status_label": (
            dict(StructureDraft.STATUS_CHOICES).get(draft.status, draft.status)
            if draft
            else "—"
        ),
        "confidence_label": (
            dict(StructureDraft.CONFIDENCE_CHOICES).get(
                draft.confidence, draft.confidence or "—"
            )
            if draft
            else "—"
        ),
        "version_label": f"v{draft.version}" if draft else "—",
        "recent_applies": list(
            ScoutApply.objects.filter(project=scout_project)
            .select_related("target_project", "created_by")
            .order_by("-created_at")[:10]
        ),
    }


def preview_overwrite(user, scout_project: Project, target_id: str) -> dict | None:
    target = _resolve_target(user, scout_project, target_id)
    if target is None:
        return None
    current = source_persistence_service.get_source_dict(target)
    draft = save_draft_service.get_current_draft(scout_project)
    source = (draft.payload or {}).get("source") if draft else {}
    return {
        "target_slug": target.slug,
        "target_name": target.name,
        "target_field_count": len(current.get("fields") or []),
        "scout_field_count": len((source or {}).get("fields") or []),
        "target_file_type": current.get("file_type_code") or "",
    }


def _resolve_target(user, scout_project: Project, target_id: str) -> Project | None:
    if not target_id:
        return None
    try:
        target = Project.objects.get(pk=target_id, is_archived=False)
    except (Project.DoesNotExist, ValueError):
        return None
    if target.company_id != scout_project.company_id:
        return None
    if target.project_kind not in {
        Project.KIND_FILE_GATE,
        Project.KIND_REVERSE,
    }:
        return None
    if not user_can_edit_target(user, target):
        return None
    return target


@transaction.atomic
def apply_to_target(
    user,
    scout_project: Project,
    *,
    target_id: str,
) -> OperationResult:
    if scout_project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_apply_from_scout(user, scout_project):
        return OperationResult.failure("forbidden", MSG_NO_APPLY)

    draft = save_draft_service.get_current_draft(scout_project)
    if draft is None:
        return OperationResult.failure("validation_form", MSG_NO_DRAFT)

    if not target_id:
        return OperationResult.failure("validation_form", MSG_NO_TARGET)

    target = _resolve_target(user, scout_project, target_id)
    if target is None:
        return OperationResult.failure("forbidden", MSG_TARGET_FORBIDDEN)

    source = (draft.payload or {}).get("source") or {}
    if not source.get("file_type_code") or not (source.get("fields") or []):
        return OperationResult.failure("unexpected", MSG_APPLY_FAIL)

    meta, fields_partial = map_scout_source_to_partials(source)

    try:
        result_meta = source_persistence_service.save_source(
            user, target, meta, strict=False
        )
        if not result_meta.ok:
            ScoutApply.objects.create(
                project=scout_project,
                draft=draft,
                draft_version=draft.version,
                target_project=target,
                target_kind=target.project_kind,
                status=ScoutApply.STATUS_FAILED,
                message=result_meta.user_message or MSG_APPLY_FAIL,
                created_by=user,
            )
            return OperationResult.failure(
                result_meta.error_code or "unexpected",
                result_meta.user_message or MSG_APPLY_FAIL,
                errors=result_meta.errors,
            )

        result_fields = source_persistence_service.save_source(
            user, target, fields_partial, strict=False
        )
        if not result_fields.ok:
            ScoutApply.objects.create(
                project=scout_project,
                draft=draft,
                draft_version=draft.version,
                target_project=target,
                target_kind=target.project_kind,
                status=ScoutApply.STATUS_FAILED,
                message=result_fields.user_message or MSG_APPLY_FAIL,
                created_by=user,
            )
            return OperationResult.failure(
                result_fields.error_code or "unexpected",
                result_fields.user_message or MSG_APPLY_FAIL,
                errors=result_fields.errors,
            )
    except Exception:
        logger.exception(
            "apply_to_target unexpected scout=%s target=%s",
            scout_project.slug,
            target.slug,
        )
        ScoutApply.objects.create(
            project=scout_project,
            draft=draft,
            draft_version=draft.version,
            target_project=target,
            target_kind=target.project_kind,
            status=ScoutApply.STATUS_FAILED,
            message=MSG_APPLY_FAIL,
            created_by=user,
        )
        return OperationResult.failure("unexpected", MSG_APPLY_FAIL)

    apply_row = ScoutApply.objects.create(
        project=scout_project,
        draft=draft,
        draft_version=draft.version,
        target_project=target,
        target_kind=target.project_kind,
        status=ScoutApply.STATUS_OK,
        message=MSG_APPLY_OK,
        created_by=user,
    )
    scout_project.save(update_fields=["updated_at"])

    deep_link = target_deep_link(target)
    return OperationResult.success(
        user_message=MSG_APPLY_OK,
        payload={
            "apply": apply_row,
            "target": target,
            "deep_link": deep_link,
        },
    )
