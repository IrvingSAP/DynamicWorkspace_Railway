"""Propuesta de campos STRUCTURE SCOUT M4 (propose_fields.md)."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.constants import PREVIEW_LINE_LIMIT
from apps.dms.file_intake.services import detection_service
from apps.dms.source_profile.services.source_profile_service import (
    get_content_type_choices,
)
from apps.dms.transform_execution.services.source_field_validation_service import (
    CONTENT_TYPE_PATTERNS,
    DATE_FORMAT_MAP,
)
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service
from apps.structure_scout.detect.services import detect_pattern_service
from apps.structure_scout.models import ScoutDetectionState, ScoutFieldsState
from apps.structure_scout.sample.services import sample_upload_service

logger = logging.getLogger(__name__)

MSG_NO_DETECTION = "Confirme el patrón de detección antes de proponer campos."
MSG_NO_SAMPLE = "Suba una muestra antes de proponer campos."
MSG_CONFIRM_OK = "Campos propuestos y confirmados."
MSG_CONFIRM_REVIEW = (
    "Campos guardados con revisión pendiente. Revise tipos antes de guardar el borrador."
)
MSG_REINFER_OK = "Campos vueltos a inferir desde la muestra."
MSG_NO_EDIT = "No tiene permiso para editar los campos propuestos."
MSG_NO_CONFIRM = "No tiene permiso para confirmar los campos."
MSG_EMPTY = "Agregue al menos un campo."
MSG_NAME_REQUIRED = "Indique el nombre del campo."
MSG_NAME_DUP = "El nombre del campo debe ser único."
MSG_TYPE_INVALID = "Seleccione un tipo de contenido válido."
MSG_INFER_FAIL = (
    "No se pudieron inferir campos desde la muestra. Revise el patrón o la muestra."
)
MSG_VALIDATION = "Revise los datos de los campos propuestos."

_NAME_SAFE = re.compile(r"[^A-Za-z0-9_]+")
_DECIMAL_COMMA = re.compile(r"^[0-9]+(,[0-9]+)?$")

# Prefer specific types when match rates tie.
_TYPE_PRIORITY = (
    "numeric",
    "decimal",
    "date",
    "datetime",
    "alpha",
    "alphanumeric",
    "alphanumeric_spaces",
    "free_text",
    "custom",
)


def user_can_edit_fields(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED)


def user_can_confirm(user, project: Project) -> bool:
    membership = project_service.get_membership(user, project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_GE,
    )


def user_can_reinfer(user, project: Project) -> bool:
    return sample_upload_service.user_can_upload_sample(user, project)


def get_or_none_state(project: Project) -> ScoutFieldsState | None:
    return getattr(project, "scout_fields", None) or ScoutFieldsState.objects.filter(
        project=project
    ).select_related("sample", "detection", "confirmed_by").first()


def has_confirmed_fields(project: Project) -> bool:
    state = get_or_none_state(project)
    if state is None:
        return False
    return state.status in (
        ScoutFieldsState.STATUS_DRAFT_READY,
        ScoutFieldsState.STATUS_NEEDS_REVIEW,
    )


def _valid_content_types() -> set[str]:
    return {item["code"] for item in get_content_type_choices()}


def _sanitize_name(raw: str, index: int) -> str:
    text = (raw or "").strip()
    text = text.replace(" ", "_")
    text = _NAME_SAFE.sub("_", text).strip("_")
    if not text:
        return f"col_{index}"
    if text[0].isdigit():
        text = f"f_{text}"
    return text[:80]


def _split_line(raw: str, delimiter: str) -> list[str]:
    if delimiter:
        return [part.strip() for part in raw.split(delimiter)]
    return [raw.strip()] if raw.strip() else [""]


def _matches_any_date(value: str) -> bool:
    for fmt in DATE_FORMAT_MAP.values():
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    # ISO-ish datetime
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def _cell_matches(content_type: str, value: str) -> bool:
    if content_type in CONTENT_TYPE_PATTERNS:
        if CONTENT_TYPE_PATTERNS[content_type].fullmatch(value):
            return True
        if content_type == "decimal" and _DECIMAL_COMMA.fullmatch(value):
            return True
        return False
    if content_type == "date":
        return _matches_any_date(value) and " " not in value and "T" not in value
    if content_type == "datetime":
        return _matches_any_date(value)
    if content_type in {"free_text", "custom"}:
        return True
    return False


def _infer_column(
    values: list[str],
    *,
    name: str,
    force_low: bool = False,
) -> dict:
    nonempty = [v for v in values if v.strip()]
    examples = nonempty[:3]
    notes = ""

    if not nonempty:
        return {
            "name": name,
            "content_type": "free_text",
            "required": False,
            "confidence": ScoutFieldsState.CONFIDENCE_LOW,
            "examples": [],
            "notes": "empty_column",
        }

    scores: dict[str, int] = {}
    for ctype in _TYPE_PRIORITY:
        if ctype in {"free_text", "custom"}:
            continue
        scores[ctype] = sum(1 for v in nonempty if _cell_matches(ctype, v))

    best = max(scores, key=lambda k: (scores[k], -_TYPE_PRIORITY.index(k)))
    ratio = scores[best] / len(nonempty) if nonempty else 0

    # Mixed separators note for decimal
    if best == "decimal":
        has_dot = any("." in v for v in nonempty)
        has_comma = any("," in v for v in nonempty)
        if has_dot and has_comma:
            notes = "mixed_decimal_separators"

    if best == "date" and ratio < 1.0:
        notes = notes or "mixed_date_formats"

    if ratio >= 0.8 and len(nonempty) >= 3 and not force_low:
        confidence = ScoutFieldsState.CONFIDENCE_HIGH
        content_type = best
    elif ratio >= 0.5 and not force_low:
        confidence = ScoutFieldsState.CONFIDENCE_MEDIUM
        content_type = best if ratio >= 0.5 else "free_text"
        if ratio < 0.8:
            notes = notes or "mixed_types"
    else:
        confidence = ScoutFieldsState.CONFIDENCE_LOW
        content_type = best if ratio >= 0.5 else "free_text"
        notes = notes or ("low_coverage" if len(nonempty) < 3 else "mixed_types")

    if force_low:
        confidence = ScoutFieldsState.CONFIDENCE_LOW

    return {
        "name": name,
        "content_type": content_type,
        "required": False,
        "confidence": confidence,
        "examples": examples,
        "notes": notes,
    }


def _global_status_and_confidence(
    fields: list[dict],
    *,
    detection: ScoutDetectionState | None,
) -> tuple[str, str, str]:
    if not fields:
        return "", ScoutFieldsState.STATUS_FAILED, "Sin columnas."

    confs = [f.get("confidence") or ScoutFieldsState.CONFIDENCE_LOW for f in fields]
    notes_parts = []

    force_review = False
    if detection is not None:
        if detection.file_type_code in {"txt_fixed", "xlsx"}:
            force_review = True
            notes_parts.append(detection.file_type_code)
        if detection.status == ScoutDetectionState.STATUS_NEEDS_REVIEW:
            force_review = True

    if any(c == ScoutFieldsState.CONFIDENCE_LOW for c in confs):
        global_conf = ScoutFieldsState.CONFIDENCE_LOW
        force_review = True
    elif any(c == ScoutFieldsState.CONFIDENCE_MEDIUM for c in confs):
        global_conf = ScoutFieldsState.CONFIDENCE_MEDIUM
        force_review = True
    else:
        global_conf = ScoutFieldsState.CONFIDENCE_HIGH

    data_rows_hint = max((len(f.get("examples") or []) for f in fields), default=0)
    if data_rows_hint < 3:
        force_review = True
        notes_parts.append("low_row_coverage")

    status = (
        ScoutFieldsState.STATUS_NEEDS_REVIEW
        if force_review
        else ScoutFieldsState.STATUS_DRAFT_READY
    )
    return global_conf, status, "; ".join(notes_parts)


def infer_fields_from_sample(
    sample,
    detection: ScoutDetectionState,
) -> tuple[list[dict], str]:
    """Returns (fields, error_note). error_note empty on success."""
    try:
        preview = detection_service.preview_rows(
            sample.stored_path,
            filename=sample.original_filename,
            limit=PREVIEW_LINE_LIMIT,
        )
    except Exception:
        logger.exception("infer preview sample=%s", sample.id)
        return [], MSG_INFER_FAIL

    delimiter = detection.delimiter or ""
    file_type = detection.file_type_code or ""
    force_low = file_type in {"txt_fixed", "xlsx"}

    if file_type == "txt_fixed" and not delimiter:
        # Single weak column per line
        rows = [[(item.get("raw") or "").rstrip("\n\r")] for item in preview]
    else:
        rows = [
            _split_line(item.get("raw") or "", delimiter) for item in preview
        ]

    if not rows:
        return [], MSG_INFER_FAIL

    # Determine width
    width = max((len(r) for r in rows), default=0)
    if width == 0:
        return [], MSG_INFER_FAIL

    # Normalize row lengths
    normalized = [r + [""] * (width - len(r)) for r in rows]

    has_header = bool(detection.has_header)
    header_row = detection.header_row or 1
    header_idx = (header_row - 1) if has_header else -1

    names: list[str] = []
    data_start = 0
    if has_header and 0 <= header_idx < len(normalized):
        header_cells = normalized[header_idx]
        used: set[str] = set()
        for i, cell in enumerate(header_cells, start=1):
            base = _sanitize_name(cell, i)
            name = base
            n = 2
            while name.lower() in used:
                name = f"{base}_{n}"
                n += 1
            used.add(name.lower())
            names.append(name)
        data_start = header_idx + 1
    else:
        names = [f"col_{i}" for i in range(1, width + 1)]

    data_rows = normalized[data_start:]
    fields: list[dict] = []
    for col_i, name in enumerate(names):
        col_values = [row[col_i] for row in data_rows if col_i < len(row)]
        fields.append(_infer_column(col_values, name=name, force_low=force_low))

    if not fields:
        return [], MSG_INFER_FAIL
    return fields, ""


def get_hub_context(user, project: Project) -> dict:
    membership = project_service.get_membership(user, project)
    sample = sample_upload_service.latest_sample(project)
    detection = detect_pattern_service.get_or_none_state(project)
    has_detection = detect_pattern_service.has_confirmed_detection(project)
    state = get_or_none_state(project)
    can_edit = user_can_edit_fields(user, project)
    can_confirm = user_can_confirm(user, project)
    can_reinfer = user_can_reinfer(user, project)
    can_preview = sample_upload_service.user_can_view_preview(user, project)

    fields: list[dict] = []
    infer_note = ""
    confidence = ""
    status = ScoutFieldsState.STATUS_IDLE
    global_notes = ""

    if has_detection and sample is not None and detection is not None:
        if (
            state
            and state.sample_id == sample.id
            and state.fields
            and state.status != ScoutFieldsState.STATUS_FAILED
        ):
            fields = list(state.fields)
            confidence = state.confidence
            status = state.status
            global_notes = state.notes or ""
        else:
            fields, infer_note = infer_fields_from_sample(sample, detection)
            if fields:
                confidence, _est_status, global_notes = _global_status_and_confidence(
                    fields, detection=detection
                )
                status = ScoutFieldsState.STATUS_IDLE
            else:
                status = ScoutFieldsState.STATUS_FAILED

    if state and state.status in (
        ScoutFieldsState.STATUS_DRAFT_READY,
        ScoutFieldsState.STATUS_NEEDS_REVIEW,
    ):
        status = state.status
        confidence = state.confidence
        global_notes = state.notes or global_notes

    # Strip examples for CO
    display_fields = []
    for item in fields:
        row = dict(item)
        if not can_preview:
            row["examples"] = []
        display_fields.append(row)

    content_types = get_content_type_choices()

    return {
        "membership": membership,
        "sample": sample,
        "detection": detection,
        "state": state,
        "fields": display_fields,
        "field_count": len(display_fields),
        "confidence": confidence,
        "status": status,
        "status_label": dict(ScoutFieldsState.STATUS_CHOICES).get(status, status),
        "confidence_label": dict(ScoutFieldsState.CONFIDENCE_CHOICES).get(
            confidence, confidence or "—"
        ),
        "global_notes": global_notes,
        "infer_note": infer_note,
        "can_edit": can_edit,
        "can_confirm": can_confirm,
        "can_reinfer": can_reinfer,
        "can_preview": can_preview,
        "has_sample": sample is not None,
        "has_detection": has_detection,
        "content_types": content_types,
        "errors": {},
        "field_errors": {},
    }


def fields_from_request(post) -> list[dict]:
    try:
        count = int(post.get("field_count") or 0)
    except (TypeError, ValueError):
        count = 0
    count = max(0, min(count, 200))
    fields: list[dict] = []
    for i in range(count):
        name = (post.get(f"name_{i}") or "").strip()
        content_type = (post.get(f"content_type_{i}") or "").strip()
        required = post.get(f"required_{i}") in ("1", "true", "on", "yes")
        notes = (post.get(f"notes_{i}") or "").strip()
        confidence = (post.get(f"confidence_{i}") or "").strip()
        examples_raw = post.get(f"examples_{i}") or ""
        if isinstance(examples_raw, str) and examples_raw.startswith("["):
            # ignore raw json; prefer pipe-separated
            examples = []
        else:
            examples = [
                part.strip()
                for part in str(examples_raw).split(" · ")
                if part.strip()
            ][:5]
            if not examples and examples_raw:
                examples = [
                    part.strip()
                    for part in str(examples_raw).split("|")
                    if part.strip()
                ][:5]
        fields.append(
            {
                "name": name,
                "content_type": content_type,
                "required": required,
                "confidence": confidence or ScoutFieldsState.CONFIDENCE_MEDIUM,
                "examples": examples,
                "notes": notes,
            }
        )
    return fields


def validate_fields(fields: list[dict]) -> dict:
    errors: dict = {}
    if not fields:
        errors["form"] = [MSG_EMPTY]
        return errors

    valid_types = _valid_content_types()
    seen: set[str] = set()
    field_errors: dict[str, dict] = {}

    for i, item in enumerate(fields):
        row_err: dict[str, list[str]] = {}
        name = (item.get("name") or "").strip()
        if not name:
            row_err["name"] = [MSG_NAME_REQUIRED]
        else:
            key = name.lower()
            if key in seen:
                row_err["name"] = [MSG_NAME_DUP]
            seen.add(key)

        ctype = (item.get("content_type") or "").strip()
        if ctype not in valid_types:
            row_err["content_type"] = [MSG_TYPE_INVALID]

        if row_err:
            field_errors[str(i)] = row_err

    if field_errors:
        errors["fields"] = field_errors
    return errors


def _persist_state(
    *,
    project: Project,
    sample,
    detection: ScoutDetectionState,
    fields: list[dict],
    status: str,
    confidence: str,
    notes: str,
    user,
    confirmed: bool,
) -> ScoutFieldsState:
    state, _created = ScoutFieldsState.objects.get_or_create(project=project)
    state.sample = sample
    state.detection = detection
    state.fields = fields
    state.status = status
    state.confidence = confidence
    state.notes = notes
    if confirmed:
        state.confirmed_at = timezone.now()
        state.confirmed_by = user
    else:
        state.confirmed_at = None
        state.confirmed_by = None
    state.save()
    project.save(update_fields=["updated_at"])
    return state


@transaction.atomic
def reinfer_fields(user, project: Project) -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_reinfer(user, project):
        return OperationResult.failure("forbidden", MSG_NO_EDIT)

    sample = sample_upload_service.latest_sample(project)
    if sample is None:
        return OperationResult.failure("validation_form", MSG_NO_SAMPLE)

    if not detect_pattern_service.has_confirmed_detection(project):
        return OperationResult.failure("validation_form", MSG_NO_DETECTION)

    detection = detect_pattern_service.get_or_none_state(project)
    if detection is None:
        return OperationResult.failure("validation_form", MSG_NO_DETECTION)

    fields, err = infer_fields_from_sample(sample, detection)
    if err or not fields:
        return OperationResult.failure("unexpected", err or MSG_INFER_FAIL)

    conf, _status, notes = _global_status_and_confidence(fields, detection=detection)
    state = _persist_state(
        project=project,
        sample=sample,
        detection=detection,
        fields=fields,
        status=ScoutFieldsState.STATUS_IDLE,
        confidence=conf,
        notes=notes,
        user=user,
        confirmed=False,
    )
    return OperationResult.success(
        user_message=MSG_REINFER_OK,
        payload={"state": state},
    )


@transaction.atomic
def confirm_fields(user, project: Project, fields: list[dict]) -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_confirm(user, project):
        return OperationResult.failure("forbidden", MSG_NO_CONFIRM)

    sample = sample_upload_service.latest_sample(project)
    if sample is None:
        return OperationResult.failure("validation_form", MSG_NO_SAMPLE)

    if not detect_pattern_service.has_confirmed_detection(project):
        return OperationResult.failure("validation_form", MSG_NO_DETECTION)

    detection = detect_pattern_service.get_or_none_state(project)
    if detection is None:
        return OperationResult.failure("validation_form", MSG_NO_DETECTION)

    if user_can_edit_fields(user, project):
        posted = fields
    else:
        # GE: accept current inferred / stored fields
        state = get_or_none_state(project)
        if state and state.fields and state.sample_id == sample.id:
            posted = list(state.fields)
        else:
            posted, err = infer_fields_from_sample(sample, detection)
            if err or not posted:
                return OperationResult.failure("unexpected", err or MSG_INFER_FAIL)

    # Preserve examples from previous inference when editor cleared them
    if user_can_edit_fields(user, project):
        prev = get_or_none_state(project)
        prev_fields = (prev.fields if prev else None) or []
        if not prev_fields:
            inferred, _err = infer_fields_from_sample(sample, detection)
            prev_fields = inferred
        for i, item in enumerate(posted):
            if not item.get("examples") and i < len(prev_fields):
                item["examples"] = prev_fields[i].get("examples") or []
            if not item.get("confidence") and i < len(prev_fields):
                item["confidence"] = prev_fields[i].get("confidence") or (
                    ScoutFieldsState.CONFIDENCE_MEDIUM
                )

    errors = validate_fields(posted)
    if errors:
        return OperationResult.failure(
            "validation_form",
            MSG_VALIDATION,
            errors=errors,
        )

    conf, status, notes = _global_status_and_confidence(posted, detection=detection)
    if status == ScoutFieldsState.STATUS_FAILED:
        return OperationResult.failure("validation_form", MSG_INFER_FAIL)

    state = _persist_state(
        project=project,
        sample=sample,
        detection=detection,
        fields=posted,
        status=status,
        confidence=conf,
        notes=notes,
        user=user,
        confirmed=True,
    )
    message = (
        MSG_CONFIRM_REVIEW
        if status == ScoutFieldsState.STATUS_NEEDS_REVIEW
        else MSG_CONFIRM_OK
    )
    return OperationResult.success(
        user_message=message,
        payload={"state": state},
    )
