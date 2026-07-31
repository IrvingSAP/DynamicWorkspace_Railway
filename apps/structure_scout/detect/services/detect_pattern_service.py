"""Detección de patrón STRUCTURE SCOUT M3 (detect_pattern.md)."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.dms.file_intake.constants import PREVIEW_LINE_LIMIT
from apps.dms.file_intake.services import detection_service
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service
from apps.structure_scout.models import ScoutDetectionState
from apps.structure_scout.sample.services import sample_upload_service

logger = logging.getLogger(__name__)

FILE_TYPE_CHOICES = (
    ("csv", "csv"),
    ("xlsx", "xlsx"),
    ("txt_delimited", "txt_delimited"),
    ("txt_fixed", "txt_fixed"),
)

ENCODING_CHOICES = (
    ("utf-8", "utf-8"),
    ("latin-1", "latin-1"),
)

LINE_ENDING_CHOICES = (
    ("lf", "lf"),
    ("crlf", "crlf"),
    ("cr", "cr"),
)

DELIMITER_CHOICES = (
    (",", ", (coma)"),
    (";", "; (punto y coma)"),
    ("\t", "tab"),
    ("|", "|"),
    ("", "(ninguno / fijo)"),
)

MSG_NO_SAMPLE = "Suba una muestra antes de detectar el patrón."
MSG_CONFIRM_OK = "Patrón detectado y confirmado."
MSG_CONFIRM_REVIEW = (
    "Patrón guardado con revisión pendiente. Revise antes de aplicar a un destino."
)
MSG_RERUN_OK = "Sugerencias actualizadas desde la muestra."
MSG_NO_EDIT = "No tiene permiso para editar el patrón de detección."
MSG_NO_CONFIRM = "No tiene permiso para confirmar el patrón de detección."
MSG_TYPE_REQUIRED = "Seleccione un tipo de archivo."
MSG_DELIM_REQUIRED = "Indique el delimitador o cambie el tipo."
MSG_HEADER_ROW = "La fila de encabezado debe ser ≥ 1."
MSG_READ_FAIL = "No se pudo analizar la muestra. Vuelva a subir el archivo."


def user_can_edit_pattern(user, project: Project) -> bool:
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


def user_can_rerun(user, project: Project) -> bool:
    return sample_upload_service.user_can_upload_sample(user, project)


def get_or_none_state(project: Project) -> ScoutDetectionState | None:
    return getattr(project, "scout_detection", None) or ScoutDetectionState.objects.filter(
        project=project
    ).select_related("sample", "confirmed_by").first()


def has_confirmed_detection(project: Project) -> bool:
    state = get_or_none_state(project)
    if state is None:
        return False
    return state.status in (
        ScoutDetectionState.STATUS_DRAFT_READY,
        ScoutDetectionState.STATUS_NEEDS_REVIEW,
    )


def _guess_has_header(preview_rows: list[dict], delimiter: str | None) -> bool:
    if not preview_rows:
        return True
    raw = (preview_rows[0].get("raw") or "").strip()
    if not raw:
        return True
    if delimiter:
        cells = raw.split(delimiter)
    else:
        cells = [raw]
    alphaish = 0
    for cell in cells:
        token = cell.strip()
        if token and any(ch.isalpha() for ch in token):
            alphaish += 1
    return alphaish >= max(1, len(cells) // 2)


def _compute_confidence_and_status(
    *,
    file_type_code: str,
    delimiter: str,
    has_header: bool,
    preview_rows: list[dict],
) -> tuple[str, str, str]:
    """Returns confidence, status, notes."""
    notes = ""
    if not file_type_code:
        return "", ScoutDetectionState.STATUS_FAILED, "Sin tipo de archivo."

    if file_type_code == "txt_fixed":
        return (
            ScoutDetectionState.CONFIDENCE_LOW,
            ScoutDetectionState.STATUS_NEEDS_REVIEW,
            "TXT posicional requiere revisión manual de longitudes.",
        )

    if file_type_code == "txt_delimited" and not delimiter:
        return (
            ScoutDetectionState.CONFIDENCE_LOW,
            ScoutDetectionState.STATUS_NEEDS_REVIEW,
            "Tipo delimitado sin delimitador claro.",
        )

    if len(preview_rows) < 3:
        return (
            ScoutDetectionState.CONFIDENCE_MEDIUM,
            ScoutDetectionState.STATUS_NEEDS_REVIEW,
            "Pocas filas en el preview; cobertura baja.",
        )

    if file_type_code in {"csv", "txt_delimited"} and delimiter:
        # Check stable column counts on first rows
        counts = []
        for row in preview_rows[:10]:
            raw = row.get("raw") or ""
            counts.append(raw.count(delimiter))
        if counts and min(counts) > 0 and max(counts) == min(counts):
            conf = ScoutDetectionState.CONFIDENCE_HIGH
            status = ScoutDetectionState.STATUS_DRAFT_READY
            if not has_header:
                notes = "Sin encabezado declarado."
            return conf, status, notes
        return (
            ScoutDetectionState.CONFIDENCE_MEDIUM,
            ScoutDetectionState.STATUS_NEEDS_REVIEW,
            "El número de columnas por fila no es estable.",
        )

    if file_type_code == "xlsx":
        return (
            ScoutDetectionState.CONFIDENCE_MEDIUM,
            ScoutDetectionState.STATUS_NEEDS_REVIEW,
            "Preview Excel limitado en MVP.",
        )

    return (
        ScoutDetectionState.CONFIDENCE_MEDIUM,
        ScoutDetectionState.STATUS_NEEDS_REVIEW,
        "",
    )


def _split_preview(preview_rows: list[dict], delimiter: str) -> list[dict]:
    rows = []
    for item in preview_rows:
        raw = item.get("raw") or ""
        if delimiter:
            parts = raw.split(delimiter)
            parsed = " | ".join(parts)
        else:
            parsed = raw
        rows.append(
            {
                "line": item.get("line"),
                "raw": raw,
                "parsed": parsed,
            }
        )
    return rows


def _suggestions_to_form(suggestions: dict, preview_rows: list[dict]) -> dict:
    file_type = (suggestions.get("file_type_code") or "").strip()
    delimiter = suggestions.get("delimiter")
    if delimiter is None:
        delimiter = ""
    encoding = (suggestions.get("encoding_code") or "utf-8").strip() or "utf-8"
    line_ending = (suggestions.get("line_ending_code") or "lf").strip() or "lf"
    has_header = _guess_has_header(preview_rows, delimiter or None)
    return {
        "file_type_code": file_type,
        "encoding_code": encoding,
        "line_ending_code": line_ending,
        "delimiter": delimiter,
        "has_header": has_header,
        "header_row": 1 if has_header else None,
        "notes": "",
    }


def build_live_suggestions(sample) -> tuple[dict, list[dict]]:
    try:
        suggestions = detection_service.build_suggestions(
            sample.original_filename, sample.stored_path
        )
        preview = detection_service.preview_rows(
            sample.stored_path,
            filename=sample.original_filename,
            limit=PREVIEW_LINE_LIMIT,
        )
        return suggestions, preview
    except Exception:
        logger.exception("detect build_live_suggestions sample=%s", sample.id)
        return {}, []


def get_hub_context(user, project: Project) -> dict:
    membership = project_service.get_membership(user, project)
    sample = sample_upload_service.latest_sample(project)
    state = get_or_none_state(project)
    can_edit = user_can_edit_pattern(user, project)
    can_confirm = user_can_confirm(user, project)
    can_rerun = user_can_rerun(user, project)
    can_preview = sample_upload_service.user_can_view_preview(user, project)

    suggestions: dict = {}
    preview_rows: list[dict] = []
    posted = {
        "file_type_code": "",
        "encoding_code": "utf-8",
        "line_ending_code": "lf",
        "delimiter": "",
        "has_header": True,
        "header_row": 1,
        "notes": "",
    }

    if sample is not None:
        if state and state.sample_id == sample.id and state.status != ScoutDetectionState.STATUS_IDLE:
            posted = {
                "file_type_code": state.file_type_code,
                "encoding_code": state.encoding_code or "utf-8",
                "line_ending_code": state.line_ending_code or "lf",
                "delimiter": state.delimiter or "",
                "has_header": state.has_header,
                "header_row": state.header_row,
                "notes": state.notes or "",
            }
            suggestions = state.suggestions_snapshot or sample.suggestions or {}
        else:
            suggestions = sample.suggestions or {}
            if not suggestions:
                suggestions, preview_rows = build_live_suggestions(sample)
            else:
                preview_rows = detection_service.preview_rows(
                    sample.stored_path,
                    filename=sample.original_filename,
                    limit=PREVIEW_LINE_LIMIT,
                )
            posted = _suggestions_to_form(suggestions, preview_rows)

        if not preview_rows and can_preview:
            preview_rows = detection_service.preview_rows(
                sample.stored_path,
                filename=sample.original_filename,
                limit=PREVIEW_LINE_LIMIT,
            )

    if not can_preview:
        preview_rows = []

    split_rows = _split_preview(preview_rows, posted.get("delimiter") or "")

    confidence = state.confidence if state else ""
    status = state.status if state else ScoutDetectionState.STATUS_IDLE
    if state is None and sample is not None:
        conf, _status_est, _notes = _compute_confidence_and_status(
            file_type_code=posted.get("file_type_code") or "",
            delimiter=posted.get("delimiter") or "",
            has_header=bool(posted.get("has_header")),
            preview_rows=preview_rows,
        )
        confidence = conf
        # Preview-only estimate; not persisted until confirm
        status = ScoutDetectionState.STATUS_IDLE

    return {
        "membership": membership,
        "sample": sample,
        "state": state,
        "posted": posted,
        "suggestions": suggestions,
        "preview_rows": preview_rows,
        "split_rows": split_rows,
        "confidence": confidence,
        "status": status,
        "status_label": dict(ScoutDetectionState.STATUS_CHOICES).get(status, status),
        "confidence_label": dict(ScoutDetectionState.CONFIDENCE_CHOICES).get(
            confidence, confidence or "—"
        ),
        "can_edit": can_edit,
        "can_confirm": can_confirm,
        "can_rerun": can_rerun,
        "can_preview": can_preview,
        "has_sample": sample is not None,
        "file_type_choices": FILE_TYPE_CHOICES,
        "encoding_choices": ENCODING_CHOICES,
        "line_ending_choices": LINE_ENDING_CHOICES,
        "delimiter_choices": DELIMITER_CHOICES,
        "errors": {},
    }


def posted_from_request(post) -> dict:
    has_header = post.get("has_header") in ("1", "true", "on", "yes")
    header_raw = (post.get("header_row") or "").strip()
    header_row = None
    if has_header and header_raw:
        try:
            header_row = int(header_raw)
        except ValueError:
            header_row = -1
    elif has_header:
        header_row = 1
    return {
        "file_type_code": (post.get("file_type_code") or "").strip(),
        "encoding_code": (post.get("encoding_code") or "utf-8").strip() or "utf-8",
        "line_ending_code": (post.get("line_ending_code") or "lf").strip() or "lf",
        "delimiter": post.get("delimiter", ""),
        "has_header": has_header,
        "header_row": header_row,
        "notes": (post.get("notes") or "").strip(),
    }


def validate_pattern(data: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    file_type = data.get("file_type_code") or ""
    valid_types = {item[0] for item in FILE_TYPE_CHOICES}
    if file_type not in valid_types:
        errors.setdefault("file_type_code", []).append(MSG_TYPE_REQUIRED)

    encoding = data.get("encoding_code") or ""
    if encoding not in {item[0] for item in ENCODING_CHOICES}:
        errors.setdefault("encoding_code", []).append("Seleccione un encoding válido.")

    le = data.get("line_ending_code") or ""
    if le not in {item[0] for item in LINE_ENDING_CHOICES}:
        errors.setdefault("line_ending_code", []).append("Seleccione un fin de línea válido.")

    delim = data.get("delimiter", "")
    if delim not in {item[0] for item in DELIMITER_CHOICES}:
        errors.setdefault("delimiter", []).append("Seleccione un delimitador válido.")

    if file_type in {"csv", "txt_delimited"} and not delim:
        errors.setdefault("delimiter", []).append(MSG_DELIM_REQUIRED)

    if data.get("has_header"):
        header_row = data.get("header_row")
        if header_row is None or header_row < 1:
            errors.setdefault("header_row", []).append(MSG_HEADER_ROW)

    return errors


@transaction.atomic
def rerun_detection(user, project: Project) -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_rerun(user, project):
        return OperationResult.failure("forbidden", MSG_NO_EDIT)

    sample = sample_upload_service.latest_sample(project)
    if sample is None:
        return OperationResult.failure("validation_form", MSG_NO_SAMPLE)

    suggestions, preview = build_live_suggestions(sample)
    if not suggestions and not preview:
        return OperationResult.failure("unexpected", MSG_READ_FAIL)

    sample.suggestions = suggestions
    sample.save(update_fields=["suggestions"])

    form = _suggestions_to_form(suggestions, preview)
    conf, status, notes = _compute_confidence_and_status(
        file_type_code=form["file_type_code"],
        delimiter=form["delimiter"] or "",
        has_header=form["has_header"],
        preview_rows=preview,
    )

    state, _created = ScoutDetectionState.objects.get_or_create(project=project)
    state.sample = sample
    state.file_type_code = form["file_type_code"]
    state.encoding_code = form["encoding_code"]
    state.line_ending_code = form["line_ending_code"]
    state.delimiter = form["delimiter"] or ""
    state.has_header = form["has_header"]
    state.header_row = form["header_row"]
    state.confidence = conf
    state.status = ScoutDetectionState.STATUS_IDLE
    state.notes = notes
    state.suggestions_snapshot = suggestions
    state.confirmed_at = None
    state.confirmed_by = None
    state.save()
    project.save(update_fields=["updated_at"])

    return OperationResult.success(
        user_message=MSG_RERUN_OK,
        payload={"state": state, "preview_rows": preview},
    )


@transaction.atomic
def confirm_detection(user, project: Project, data: dict) -> OperationResult:
    if project.project_kind != Project.KIND_STRUCTURE_SCOUT:
        return OperationResult.failure(
            "forbidden", "Este proyecto no es de tipo Explorador de estructura."
        )
    if not user_can_confirm(user, project):
        return OperationResult.failure("forbidden", MSG_NO_CONFIRM)

    # GE may confirm but not apply ED/PA-style edits if they somehow POST edits:
    # if GE and form differs from last suggestions heavily — still allow confirm of posted
    # but GE cannot edit in UI (fields disabled). Server: if not can_edit, ignore overrides
    # and use current state/suggestions.
    sample = sample_upload_service.latest_sample(project)
    if sample is None:
        return OperationResult.failure("validation_form", MSG_NO_SAMPLE)

    if user_can_edit_pattern(user, project):
        posted = data
    else:
        # GE: accept current suggestions / existing idle state values
        ctx_preview = detection_service.preview_rows(
            sample.stored_path,
            filename=sample.original_filename,
            limit=PREVIEW_LINE_LIMIT,
        )
        state = get_or_none_state(project)
        if state and state.sample_id == sample.id and state.file_type_code:
            posted = {
                "file_type_code": state.file_type_code,
                "encoding_code": state.encoding_code,
                "line_ending_code": state.line_ending_code,
                "delimiter": state.delimiter,
                "has_header": state.has_header,
                "header_row": state.header_row,
                "notes": state.notes,
            }
        else:
            suggestions = sample.suggestions or {}
            if not suggestions:
                suggestions, ctx_preview = build_live_suggestions(sample)
            posted = _suggestions_to_form(suggestions, ctx_preview)

    errors = validate_pattern(posted)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos del patrón de detección.",
            errors=errors,
        )

    preview = detection_service.preview_rows(
        sample.stored_path,
        filename=sample.original_filename,
        limit=PREVIEW_LINE_LIMIT,
    )
    conf, status, auto_notes = _compute_confidence_and_status(
        file_type_code=posted["file_type_code"],
        delimiter=posted.get("delimiter") or "",
        has_header=bool(posted.get("has_header")),
        preview_rows=preview,
    )
    if status == ScoutDetectionState.STATUS_FAILED:
        return OperationResult.failure("validation_form", MSG_READ_FAIL)

    notes = (posted.get("notes") or "").strip() or auto_notes

    state, _created = ScoutDetectionState.objects.get_or_create(project=project)
    state.sample = sample
    state.file_type_code = posted["file_type_code"]
    state.encoding_code = posted["encoding_code"]
    state.line_ending_code = posted["line_ending_code"]
    state.delimiter = posted.get("delimiter") or ""
    state.has_header = bool(posted.get("has_header"))
    state.header_row = posted.get("header_row") if state.has_header else None
    state.confidence = conf
    state.status = status
    state.notes = notes
    state.suggestions_snapshot = sample.suggestions or {}
    state.confirmed_at = timezone.now()
    state.confirmed_by = user
    state.save()
    project.save(update_fields=["updated_at"])

    message = (
        MSG_CONFIRM_REVIEW
        if status == ScoutDetectionState.STATUS_NEEDS_REVIEW
        else MSG_CONFIRM_OK
    )
    return OperationResult.success(
        user_message=message,
        payload={"state": state},
    )
