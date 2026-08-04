"""Guardar borrador STRUCTURE SCOUT M5 (save_draft.md)."""

from __future__ import annotations

import copy
import json
import logging

from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse

from apps.core.services.operation_result import OperationResult
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service
from apps.structure_scout.detect.services import detect_pattern_service
from apps.structure_scout.fields.services import propose_fields_service
from apps.structure_scout.models import StructureDraft
from apps.structure_scout.sample.services import sample_upload_service

logger = logging.getLogger(__name__)

MSG_NO_FIELDS = "Confirme los campos propuestos antes de guardar el borrador."
MSG_SNAPSHOT_FAIL = "No se pudo armar el snapshot. Revise detección y campos."
MSG_SAVE_OK = "Borrador de estructura guardado (versión {version})."
MSG_NO_SAVE = "No tiene permiso para guardar el borrador de estructura."
MSG_NO_EXPORT = "No tiene permiso para exportar el borrador."
MSG_NO_DRAFT = "No hay borrador para exportar. Guarde una versión primero."
MSG_NO_ACCESS = "No tiene acceso a este proyecto Explorador."

STATUS_LABELS = dict(StructureDraft.STATUS_CHOICES)
CONFIDENCE_LABELS = dict(StructureDraft.CONFIDENCE_CHOICES)


def user_can_save(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def user_can_export(user, project: Project) -> bool:
    return project_service.get_membership(user, project) is not None


def user_can_view_examples(user, project: Project) -> bool:
    return sample_upload_service.user_can_view_preview(user, project)


def get_current_draft(project: Project) -> StructureDraft | None:
    return (
        StructureDraft.objects.filter(project=project, is_current=True)
        .select_related("created_by", "sample")
        .first()
    )


def has_current_draft(project: Project) -> bool:
    return StructureDraft.objects.filter(project=project, is_current=True).exists()


def list_versions(project: Project, *, limit: int = 20) -> list[StructureDraft]:
    return list(
        StructureDraft.objects.filter(project=project)
        .select_related("created_by")
        .order_by("-version")[:limit]
    )


def _next_version(project: Project) -> int:
    current_max = (
        StructureDraft.objects.filter(project=project).aggregate(m=Max("version"))["m"]
        or 0
    )
    return int(current_max) + 1


def _hash_short(sample) -> str:
    if sample is None:
        return ""
    return (sample.content_hash or "")[:8]


def build_payload(
    *,
    version: int,
    sample,
    detection,
    fields_state,
    strip_examples: bool = False,
) -> dict:
    fields_raw = list(fields_state.fields or [])
    product_fields = []
    source_fields = []
    for item in fields_raw:
        name = (item.get("name") or "").strip()
        content_type = (item.get("content_type") or "").strip()
        required = bool(item.get("required"))
        examples = list(item.get("examples") or [])
        if strip_examples:
            examples = []
        product_fields.append(
            {
                "name": name,
                "type": content_type,
                "content_type": content_type,
                "required": required,
                "confidence": item.get("confidence") or "",
                "examples": examples,
                "notes": item.get("notes") or "",
                "start": item.get("start"),
                "end": item.get("end"),
                "length": item.get("length"),
                "length_confidence": item.get("length_confidence") or "",
            }
        )
        source_field = {
            "name": name,
            "label": name,
            "content_type": content_type,
            "required": required,
        }
        if detection and (detection.file_type_code or "") == "txt_fixed":
            start = item.get("start")
            end = item.get("end")
            length = item.get("length")
            if start is not None:
                source_field["start"] = start
            if end is not None:
                source_field["end"] = end
            if length is not None:
                source_field["length"] = length
        source_fields.append(source_field)

    sample_block = {
        "id": str(sample.id) if sample else "",
        "filename": sample.original_filename if sample else "",
        "content_hash_short": _hash_short(sample),
    }

    detection_block = {
        "file_type_code": detection.file_type_code if detection else "",
        "encoding_code": detection.encoding_code if detection else "utf-8",
        "line_ending_code": detection.line_ending_code if detection else "lf",
        "delimiter": detection.delimiter if detection else "",
        "header_row": detection.header_row if detection else None,
        "has_header": bool(detection.has_header) if detection else True,
        "capture_start": None,
        "capture_end": None,
        "confidence": detection.confidence if detection else "",
        "status": detection.status if detection else "",
        "notes": detection.notes if detection else "",
    }

    return {
        "schema_version": "1.0",
        "kind": "structure_scout",
        "version": version,
        "status": fields_state.status,
        "confidence": fields_state.confidence or "",
        "sample": sample_block,
        "detection": detection_block,
        "draft": {"fields": product_fields},
        "source": {
            "file_type_code": detection_block["file_type_code"],
            "encoding_code": detection_block["encoding_code"],
            "line_ending_code": detection_block["line_ending_code"],
            "delimiter": detection_block["delimiter"],
            "header_row": detection_block["header_row"],
            "has_header": detection_block["has_header"],
            "fields": source_fields,
        },
        "apply": {
            "allowed_targets": [
                "file_gate",
                "reverse_studio",
                "file_match",
                "filepipe",
            ],
            "auto_publish": False,
        },
    }


def preview_snapshot(project: Project) -> dict | None:
    """Live snapshot preview (not persisted) from M3/M4."""
    if not propose_fields_service.has_confirmed_fields(project):
        return None
    fields_state = propose_fields_service.get_or_none_state(project)
    detection = detect_pattern_service.get_or_none_state(project)
    sample = sample_upload_service.latest_sample(project)
    if fields_state is None or detection is None or sample is None:
        return None
    next_ver = _next_version(project)
    return build_payload(
        version=next_ver,
        sample=sample,
        detection=detection,
        fields_state=fields_state,
        strip_examples=False,
    )


def get_hub_context(user, project: Project) -> dict:
    membership = project_service.get_membership(user, project)
    has_fields = propose_fields_service.has_confirmed_fields(project)
    fields_state = propose_fields_service.get_or_none_state(project)
    detection = detect_pattern_service.get_or_none_state(project)
    sample = sample_upload_service.latest_sample(project)
    current = get_current_draft(project)
    versions = list_versions(project)
    can_save = user_can_save(user, project)
    can_export = user_can_export(user, project)
    can_examples = user_can_view_examples(user, project)

    preview = preview_snapshot(project) if has_fields else None
    if preview and not can_examples:
        preview = _strip_payload_examples(preview)

    display_current_payload = None
    if current:
        display_current_payload = copy.deepcopy(current.payload or {})
        if not can_examples:
            display_current_payload = _strip_payload_examples(display_current_payload)

    status = current.status if current else (fields_state.status if fields_state else "")
    confidence = (
        current.confidence
        if current
        else (fields_state.confidence if fields_state else "")
    )

    return {
        "membership": membership,
        "sample": sample,
        "detection": detection,
        "fields_state": fields_state,
        "has_fields": has_fields,
        "current": current,
        "versions": versions,
        "preview": preview,
        "display_current_payload": display_current_payload,
        "can_save": can_save,
        "can_export": can_export,
        "can_examples": can_examples,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status or "—"),
        "confidence": confidence,
        "confidence_label": CONFIDENCE_LABELS.get(confidence, confidence or "—"),
        "fields_count": len((fields_state.fields if fields_state else None) or []),
        "version_label": f"v{current.version}" if current else "—",
    }


def strip_payload_examples(payload: dict) -> dict:
    return _strip_payload_examples(payload)


def _strip_payload_examples(payload: dict) -> dict:
    data = copy.deepcopy(payload or {})
    fields = (data.get("draft") or {}).get("fields") or []
    for item in fields:
        item["examples"] = []
    return data


def draft_status_label(project: Project) -> str:
    current = get_current_draft(project)
    if current is None:
        return "Sin borrador"
    status = STATUS_LABELS.get(current.status, current.status)
    return f"v{current.version} · {status}"


@transaction.atomic
def save_new_version(user, project: Project, *, notes: str = "") -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_save(user, project):
        return OperationResult.failure("forbidden", MSG_NO_SAVE)

    if not propose_fields_service.has_confirmed_fields(project):
        return OperationResult.failure("validation_form", MSG_NO_FIELDS)

    fields_state = propose_fields_service.get_or_none_state(project)
    detection = detect_pattern_service.get_or_none_state(project)
    sample = sample_upload_service.latest_sample(project)
    if fields_state is None or detection is None or sample is None:
        return OperationResult.failure("unexpected", MSG_SNAPSHOT_FAIL)

    if fields_state.status not in (
        StructureDraft.STATUS_DRAFT_READY,
        StructureDraft.STATUS_NEEDS_REVIEW,
    ):
        return OperationResult.failure("validation_form", MSG_NO_FIELDS)

    version = _next_version(project)
    payload = build_payload(
        version=version,
        sample=sample,
        detection=detection,
        fields_state=fields_state,
        strip_examples=False,
    )

    StructureDraft.objects.filter(project=project, is_current=True).update(
        is_current=False
    )

    draft = StructureDraft.objects.create(
        project=project,
        version=version,
        is_current=True,
        status=fields_state.status,
        confidence=fields_state.confidence or "",
        payload=payload,
        sample=sample,
        sample_filename=sample.original_filename,
        sample_hash_short=_hash_short(sample),
        notes=(notes or "").strip() or (fields_state.notes or ""),
        created_by=user,
    )
    project.save(update_fields=["updated_at"])

    return OperationResult.success(
        user_message=MSG_SAVE_OK.format(version=version),
        payload={"draft": draft},
    )


def export_draft_json(user, project: Project, draft: StructureDraft) -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_export(user, project):
        return OperationResult.failure("forbidden", MSG_NO_EXPORT)
    if draft is None or draft.project_id != project.id:
        return OperationResult.failure("validation_form", MSG_NO_DRAFT)

    payload = copy.deepcopy(draft.payload or {})
    if not user_can_view_examples(user, project):
        payload = _strip_payload_examples(payload)

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    filename = f"{project.slug}-structure-draft-v{draft.version}.json"
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return OperationResult.success(
        user_message="",
        payload={"response": response, "draft": draft},
    )


def export_current_json(user, project: Project) -> OperationResult:
    draft = get_current_draft(project)
    if draft is None:
        if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
            return OperationResult.failure(
                "forbidden", "Este proyecto no es de tipo Explorador de estructura."
            )
        if not user_can_export(user, project):
            return OperationResult.failure("forbidden", MSG_NO_EXPORT)
        return OperationResult.failure("validation_form", MSG_NO_DRAFT)
    return export_draft_json(user, project, draft)
