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
MSG_BOUNDS_REQUIRED = "Indique inicio/fin o longitud de cada campo posicional."
MSG_BOUNDS_ORDER = "El fin debe ser ≥ al inicio."
MSG_BOUNDS_LENGTH = "La longitud debe ser ≥ 1."
MSG_BOUNDS_OVERLAP = "Hay campos posicionales que se solapan; ajuste inicio/fin."

_NAME_SAFE = re.compile(r"[^A-Za-z0-9_]+")
_DECIMAL_COMMA = re.compile(r"^[0-9]+(,[0-9]+)?$")
_SPACE_GAP = re.compile(r" {2,}")

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


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_bounds(start, end, length) -> tuple[int | None, int | None, int | None]:
    """Sincroniza start/end/length (1-based inclusive), alineado a resolve_txt_fixed_bounds."""
    start_i = _to_int(start)
    end_i = _to_int(end)
    length_i = _to_int(length)
    if start_i is not None and length_i is not None and length_i >= 1:
        end_i = start_i + length_i - 1
    elif start_i is not None and end_i is not None and end_i >= start_i:
        length_i = end_i - start_i + 1
    elif start_i is not None and end_i is None and length_i is None:
        end_i = start_i
        length_i = 1
    return start_i, end_i, length_i


def _slice_fixed_field(sample_line: str, start, end, length) -> str:
    """Extrae el valor de un campo posicional (1-based) desde el registro de prueba."""
    sample = (sample_line or "").rstrip("\n\r")
    start_i, end_i, length_i = _resolve_bounds(start, end, length)
    if start_i is None:
        return ""
    if length_i is None or length_i < 1:
        length_i = 1
    from_idx = max(0, start_i - 1)
    chunk = sample[from_idx : from_idx + length_i]
    return chunk.rstrip()


def apply_txt_fixed_preview_examples(fields: list[dict], sample_line: str) -> None:
    """
    Ejemplos = un solo valor del registro de prueba (misma fila que Origen),
    según Inicio / Long. de cada campo — no mezcla varias filas de la muestra.
    """
    sample = (sample_line or "").rstrip("\n\r")
    for item in fields or []:
        if item.get("start") in (None, ""):
            continue
        value = _slice_fixed_field(
            sample, item.get("start"), item.get("end"), item.get("length")
        )
        item["examples"] = [value] if value else []


def _segments_by_spaces(line: str) -> list[tuple[str, int, int]]:
    """Parte una línea por huecos de 2+ espacios → (texto, start_1based, end_1based)."""
    text_line = (line or "").rstrip("\n\r")
    if not text_line.strip():
        return []
    parts: list[tuple[str, int, int]] = []
    pos = 0
    for gap in _SPACE_GAP.finditer(text_line):
        chunk = text_line[pos : gap.start()]
        if chunk.strip():
            leading = len(chunk) - len(chunk.lstrip(" "))
            value = chunk.strip()
            start = pos + leading + 1
            end = start + len(value) - 1
            parts.append((value, start, end))
        pos = gap.end()
    chunk = text_line[pos:]
    if chunk.strip():
        leading = len(chunk) - len(chunk.lstrip(" "))
        value = chunk.strip()
        start = pos + leading + 1
        end = start + len(value) - 1
        parts.append((value, start, end))
    return parts


def _apply_h2_bounds(fields: list[dict]) -> None:
    cursor = 1
    for item in fields:
        examples = item.get("examples") or []
        max_len = max((len(str(ex)) for ex in examples), default=1)
        max_len = max(1, max_len)
        item["start"] = cursor
        item["end"] = cursor + max_len - 1
        item["length"] = max_len
        item["length_confidence"] = ScoutFieldsState.CONFIDENCE_LOW
        notes = (item.get("notes") or "").strip()
        if "heuristic_max_len" not in notes:
            item["notes"] = (
                f"{notes}; heuristic_max_len".strip("; ").strip()
                if notes
                else "heuristic_max_len"
            )
        cursor = item["end"] + 1


def _apply_h3_bounds(fields: list[dict]) -> None:
    for index, item in enumerate(fields):
        start = index + 1
        item["start"] = start
        item["end"] = start
        item["length"] = 1
        item["length_confidence"] = ScoutFieldsState.CONFIDENCE_LOW
        notes = (item.get("notes") or "").strip()
        if "fallback_unit" not in notes:
            item["notes"] = (
                f"{notes}; fallback_unit".strip("; ").strip()
                if notes
                else "fallback_unit"
            )


def _try_h1_bounds_from_lines(raw_lines: list[str]) -> list[dict] | None:
    """
    H1: cortes estables por espacios múltiples en ≥3 filas con el mismo N≥2 columnas.
    Devuelve lista de {start, end, length, length_confidence, values}.
    """
    parsed: list[list[tuple[str, int, int]]] = []
    for line in raw_lines:
        segs = _segments_by_spaces(line)
        if segs:
            parsed.append(segs)
    if len(parsed) < 3:
        return None
    width = len(parsed[0])
    if width < 2:
        return None
    same = sum(1 for row in parsed if len(row) == width)
    if same < max(3, (len(parsed) + 1) // 2):
        return None

    columns: list[dict] = []
    for col_i in range(width):
        starts = [row[col_i][1] for row in parsed if len(row) == width]
        ends = [row[col_i][2] for row in parsed if len(row) == width]
        values = [row[col_i][0] for row in parsed if len(row) == width]
        start = min(starts)
        end = max(ends)
        if end < start:
            end = start
        length = end - start + 1
        columns.append(
            {
                "start": start,
                "end": end,
                "length": length,
                "length_confidence": ScoutFieldsState.CONFIDENCE_MEDIUM,
                "values": values,
            }
        )
    # Evitar solapes: si se solapan, compactar en secuencia por max length
    for i in range(1, len(columns)):
        prev = columns[i - 1]
        cur = columns[i]
        if cur["start"] <= prev["end"]:
            return None
    return columns


def _attach_txt_fixed_bounds(
    fields: list[dict],
    raw_lines: list[str],
) -> None:
    """Adjunta start/end/length a fields ya inferidos (H1→H2→H3)."""
    if not fields:
        return
    h1 = _try_h1_bounds_from_lines(raw_lines)
    if h1 is not None and len(h1) == len(fields):
        for item, bounds in zip(fields, h1):
            item["start"] = bounds["start"]
            item["end"] = bounds["end"]
            item["length"] = bounds["length"]
            item["length_confidence"] = bounds["length_confidence"]
            notes = (item.get("notes") or "").strip()
            if "heuristic_spaces" not in notes:
                item["notes"] = (
                    f"{notes}; heuristic_spaces".strip("; ").strip()
                    if notes
                    else "heuristic_spaces"
                )
        return
    if any(item.get("examples") for item in fields):
        _apply_h2_bounds(fields)
        return
    _apply_h3_bounds(fields)


def _infer_txt_fixed_via_h1(
    preview: list[dict],
    detection: ScoutDetectionState,
) -> list[dict] | None:
    raw_lines = [(item.get("raw") or "") for item in preview]
    non_empty = [line for line in raw_lines if (line or "").strip()]
    h1 = _try_h1_bounds_from_lines(non_empty)
    if h1 is None:
        return None

    has_header = bool(detection.has_header)
    names: list[str] = []
    # values are per-column lists aligned; take first row values as header if needed
    first_values = [col["values"][0] if col.get("values") else "" for col in h1]
    data_offset = 0
    if has_header:
        used: set[str] = set()
        for i, cell in enumerate(first_values, start=1):
            base = _sanitize_name(cell, i)
            name = base
            n = 2
            while name.lower() in used:
                name = f"{base}_{n}"
                n += 1
            used.add(name.lower())
            names.append(name)
        data_offset = 1
    else:
        names = [f"col_{i}" for i in range(1, len(h1) + 1)]

    fields: list[dict] = []
    for col_i, name in enumerate(names):
        col = h1[col_i]
        values = list(col.get("values") or [])[data_offset:]
        item = _infer_column(values, name=name, force_low=True)
        item["start"] = col["start"]
        item["end"] = col["end"]
        item["length"] = col["length"]
        item["length_confidence"] = col["length_confidence"]
        notes = (item.get("notes") or "").strip()
        if "heuristic_spaces" not in notes:
            item["notes"] = (
                f"{notes}; heuristic_spaces".strip("; ").strip()
                if notes
                else "heuristic_spaces"
            )
        fields.append(item)
    return fields or None


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

    if detection and (detection.file_type_code or "") == "txt_fixed":
        force_review = True
        length_confs = [
            f.get("length_confidence") or ScoutFieldsState.CONFIDENCE_LOW for f in fields
        ]
        if any(c == ScoutFieldsState.CONFIDENCE_LOW for c in length_confs):
            notes_parts.append("length_estimate_low")
        elif any(c == ScoutFieldsState.CONFIDENCE_MEDIUM for c in length_confs):
            notes_parts.append("length_estimate_medium")

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
    raw_lines = [(item.get("raw") or "") for item in preview]

    if file_type == "txt_fixed" and not delimiter:
        h1_fields = _infer_txt_fixed_via_h1(preview, detection)
        if h1_fields:
            preview_line = _first_data_line(raw_lines, detection)
            apply_txt_fixed_preview_examples(h1_fields, preview_line)
            return h1_fields, ""
        # Single weak column per line + H3 bounds
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

    if file_type == "txt_fixed":
        data_raw = raw_lines[data_start:] if data_start else raw_lines
        _attach_txt_fixed_bounds(fields, data_raw or raw_lines)
        preview_line = _first_data_line(raw_lines, detection)
        apply_txt_fixed_preview_examples(fields, preview_line)

    return fields, ""


def _digit_ruler(width: int) -> str:
    if width < 1:
        return ""
    return "".join(str((i % 10)) for i in range(1, width + 1))


def build_positional_layout(
    fields: list[dict],
    sample_line: str,
) -> dict | None:
    """
    Vista Origen / Construcción (prototipo hub_lengths):
    - Origen: regla de dígitos + registro crudo de la muestra
    - Construcción: misma regla + trozos del registro según Inicio/Long. en secuencia
    """
    sample = (sample_line or "").rstrip("\n\r")
    max_end = 0
    parts: list[str] = []
    for item in fields or []:
        start, end, length = _resolve_bounds(
            item.get("start"), item.get("end"), item.get("length")
        )
        if start is None:
            continue
        if length is None or length < 1:
            if end is not None and end >= start:
                length = end - start + 1
            else:
                length = 1
        end = start + length - 1
        max_end = max(max_end, end)
        from_idx = start - 1
        chunk = sample[from_idx : from_idx + length]
        if len(chunk) < length:
            chunk = chunk.ljust(length)
        parts.append(chunk)
    if not parts and not sample:
        return None
    built = "".join(parts)
    width = max(len(sample), max_end, len(built), 40)
    return {
        "ruler": _digit_ruler(width),
        "sample_line": sample,
        "values_line": sample.ljust(width)[:width],
        "built_line": built,
        "width": width,
    }


def _first_data_line(
    raw_lines: list[str],
    detection: ScoutDetectionState | None,
) -> str:
    lines = [(line or "").rstrip("\n\r") for line in raw_lines if (line or "").strip()]
    if not lines:
        return ""
    if detection and detection.has_header and len(lines) > 1:
        return lines[1]
    return lines[0]


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
            if (detection.file_type_code or "") == "txt_fixed" and any(
                item.get("start") in (None, "") for item in fields
            ):
                try:
                    preview = detection_service.preview_rows(
                        sample.stored_path,
                        filename=sample.original_filename,
                        limit=PREVIEW_LINE_LIMIT,
                    )
                    raw_lines = [(item.get("raw") or "") for item in preview]
                    _attach_txt_fixed_bounds(fields, raw_lines)
                except Exception:
                    logger.exception(
                        "backfill txt_fixed bounds project=%s", project.slug
                    )
                    _apply_h3_bounds(fields)
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

    # Strip examples for CO; para txt_fixed recalcular desde el registro de prueba
    display_fields = []
    for item in fields:
        row = dict(item)
        if not can_preview:
            row["examples"] = []
        display_fields.append(row)

    content_types = get_content_type_choices()
    show_bounds = bool(
        detection and (detection.file_type_code or "") == "txt_fixed"
    )

    layout_preview = None
    if show_bounds and can_preview and sample is not None and display_fields:
        try:
            preview = detection_service.preview_rows(
                sample.stored_path,
                filename=sample.original_filename,
                limit=PREVIEW_LINE_LIMIT,
            )
            raw_lines = [(item.get("raw") or "") for item in preview]
            data_line = _first_data_line(raw_lines, detection)
            apply_txt_fixed_preview_examples(display_fields, data_line)
            layout_preview = build_positional_layout(display_fields, data_line)
        except Exception:
            logger.exception("layout preview project=%s", project.slug)
            layout_preview = None

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
        "show_bounds": show_bounds,
        "layout_preview": layout_preview,
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
                "start": _to_int(post.get(f"start_{i}")),
                "end": _to_int(post.get(f"end_{i}")),
                "length": _to_int(post.get(f"length_{i}")),
                "length_confidence": (
                    post.get(f"length_confidence_{i}") or ""
                ).strip()
                or ScoutFieldsState.CONFIDENCE_LOW,
            }
        )
    return fields


def validate_fields(fields: list[dict], *, file_type_code: str = "") -> dict:
    errors: dict = {}
    if not fields:
        errors["form"] = [MSG_EMPTY]
        return errors

    valid_types = _valid_content_types()
    seen: set[str] = set()
    field_errors: dict[str, dict] = {}
    positional: list[tuple[int, int, str, int]] = []
    is_fixed = (file_type_code or "").strip() == "txt_fixed"

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

        if is_fixed:
            start, end, length = _resolve_bounds(
                item.get("start"), item.get("end"), item.get("length")
            )
            item["start"] = start
            item["end"] = end
            item["length"] = length
            if start is None or end is None or length is None:
                row_err["bounds"] = [MSG_BOUNDS_REQUIRED]
            elif length < 1:
                row_err["bounds"] = [MSG_BOUNDS_LENGTH]
            elif end < start:
                row_err["bounds"] = [MSG_BOUNDS_ORDER]
            else:
                positional.append((start, end, name or f"#{i + 1}", i))

        if row_err:
            field_errors[str(i)] = row_err

    if is_fixed and positional:
        positional.sort()
        for index in range(1, len(positional)):
            prev_start, prev_end, prev_name, prev_i = positional[index - 1]
            start, end, name, cur_i = positional[index]
            if start <= prev_end:
                msg = (
                    f"{MSG_BOUNDS_OVERLAP} "
                    f"«{prev_name}» ({prev_start}-{prev_end}) y «{name}» ({start}-{end})."
                )
                for key in (str(prev_i), str(cur_i)):
                    field_errors.setdefault(key, {}).setdefault("bounds", []).append(msg)

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
            if not item.get("length_confidence") and i < len(prev_fields):
                item["length_confidence"] = prev_fields[i].get(
                    "length_confidence"
                ) or ScoutFieldsState.CONFIDENCE_LOW

    file_type = detection.file_type_code or ""
    if file_type == "txt_fixed":
        for item in posted:
            start, end, length = _resolve_bounds(
                item.get("start"), item.get("end"), item.get("length")
            )
            item["start"] = start
            item["end"] = end
            item["length"] = length
            if not item.get("length_confidence"):
                item["length_confidence"] = ScoutFieldsState.CONFIDENCE_LOW
        try:
            preview = detection_service.preview_rows(
                sample.stored_path,
                filename=sample.original_filename,
                limit=PREVIEW_LINE_LIMIT,
            )
            raw_lines = [(item.get("raw") or "") for item in preview]
            apply_txt_fixed_preview_examples(
                posted, _first_data_line(raw_lines, detection)
            )
        except Exception:
            logger.exception(
                "confirm txt_fixed examples project=%s", project.slug
            )

    errors = validate_fields(posted, file_type_code=file_type)
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
