import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.core.services.operation_result import OperationResult
from apps.fields.models import FieldDefinition
from apps.fields.services.validators import validate_value
from apps.projects.models import ProjectMembership
from apps.projects.services import project_service
from apps.records.models import FieldValue, Record

logger = logging.getLogger(__name__)

EDIT_ROLES = {ProjectMembership.ROLE_PA, ProjectMembership.ROLE_ED}


def user_can_edit_records(user, project) -> bool:
    membership = project_service.get_membership(user, project)
    return membership is not None and membership.role in EDIT_ROLES


def get_view_context(user, slug: str):
    project = project_service.get_project_for_user(user, slug)
    if project is None:
        return None, None
    membership = project_service.get_membership(user, project)
    return project, membership


def get_record_for_project(project, record_id: str) -> Record | None:
    try:
        return Record.objects.get(pk=record_id, project=project, is_deleted=False)
    except (Record.DoesNotExist, ValueError):
        return None


def active_fields(project):
    return FieldDefinition.objects.filter(
        project=project,
        is_active=True,
    ).order_by("sort_order", "label")


def _field_input_name(field: FieldDefinition) -> str:
    return f"fv_{field.key}"


def raw_from_post(post, field: FieldDefinition):
    name = _field_input_name(field)
    if field.field_type == FieldDefinition.TYPE_BOOLEAN:
        return post.get(name) == "1"
    return post.get(name, "").strip()


def default_posted(fields) -> dict[str, Any]:
    posted: dict[str, Any] = {}
    for field in fields:
        name = _field_input_name(field)
        if field.field_type == FieldDefinition.TYPE_BOOLEAN:
            posted[name] = False
        else:
            posted[name] = ""
    return posted


def posted_from_record(record: Record, fields) -> dict[str, Any]:
    values_by_field = {fv.field_id: fv for fv in record.field_values.all()}
    posted: dict[str, Any] = {}
    for field in fields:
        name = _field_input_name(field)
        fv = values_by_field.get(field.id)
        if fv is None:
            posted[name] = False if field.field_type == FieldDefinition.TYPE_BOOLEAN else ""
            continue
        posted[name] = value_for_form(field, fv)
    return posted


def posted_from_request(post, fields) -> dict[str, Any]:
    posted: dict[str, Any] = {}
    for field in fields:
        posted[_field_input_name(field)] = raw_from_post(post, field)
    return posted


def value_for_form(field: FieldDefinition, fv: FieldValue):
    if field.field_type == FieldDefinition.TYPE_BOOLEAN:
        return bool(fv.value_boolean)
    if field.field_type in FieldDefinition.TEXT_TYPES or field.field_type == FieldDefinition.TYPE_SELECT:
        return fv.value_text or ""
    if field.field_type in FieldDefinition.NUMBER_TYPES:
        if fv.value_number is None:
            return ""
        return str(fv.value_number)
    if field.field_type == FieldDefinition.TYPE_DATE:
        return fv.value_date.isoformat() if fv.value_date else ""
    if field.field_type == FieldDefinition.TYPE_DATETIME:
        payload = fv.value_json or {}
        text = payload.get("value", "")
        if not text:
            return ""
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            return text[:16] if len(text) >= 16 else text
    return ""


def _normalize_for_storage(field: FieldDefinition, raw_value) -> Any:
    if raw_value in (None, "") and not field.required:
        return None
    if field.field_type in FieldDefinition.TEXT_TYPES or field.field_type == FieldDefinition.TYPE_SELECT:
        return str(raw_value).strip()
    if field.field_type == FieldDefinition.TYPE_INTEGER:
        return int(raw_value)
    if field.field_type == FieldDefinition.TYPE_DECIMAL:
        return Decimal(str(raw_value).replace(",", "."))
    if field.field_type == FieldDefinition.TYPE_DATE:
        if isinstance(raw_value, date):
            return raw_value
        return date.fromisoformat(str(raw_value))
    if field.field_type == FieldDefinition.TYPE_DATETIME:
        text = str(raw_value)
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    if field.field_type == FieldDefinition.TYPE_BOOLEAN:
        return raw_value in (True, "1", "on", "true", 1)
    return raw_value


def _clear_typed_columns(fv: FieldValue) -> None:
    fv.value_text = None
    fv.value_number = None
    fv.value_date = None
    fv.value_boolean = None
    fv.value_json = None


def _apply_storage(fv: FieldValue, field: FieldDefinition, stored: Any) -> None:
    _clear_typed_columns(fv)
    if stored is None:
        return
    if field.field_type in FieldDefinition.TEXT_TYPES or field.field_type == FieldDefinition.TYPE_SELECT:
        fv.value_text = stored
    elif field.field_type in FieldDefinition.NUMBER_TYPES:
        fv.value_number = stored
    elif field.field_type == FieldDefinition.TYPE_DATE:
        fv.value_date = stored
    elif field.field_type == FieldDefinition.TYPE_BOOLEAN:
        fv.value_boolean = bool(stored)
    elif field.field_type == FieldDefinition.TYPE_DATETIME:
        iso = stored.isoformat() if isinstance(stored, datetime) else str(stored)
        fv.value_json = {"value": iso}


def display_value(field: FieldDefinition, fv: FieldValue | None) -> str:
    if fv is None:
        return "—"
    if field.field_type in FieldDefinition.TEXT_TYPES or field.field_type == FieldDefinition.TYPE_SELECT:
        return fv.value_text or "—"
    if field.field_type == FieldDefinition.TYPE_INTEGER:
        if fv.value_number is None:
            return "—"
        return f"{int(fv.value_number):,}".replace(",", "\u00a0")
    if field.field_type == FieldDefinition.TYPE_DECIMAL:
        if fv.value_number is None:
            return "—"
        text = f"{fv.value_number:f}".rstrip("0").rstrip(".")
        return text.replace(".", ",")
    if field.field_type == FieldDefinition.TYPE_DATE:
        return fv.value_date.strftime("%d/%m/%Y") if fv.value_date else "—"
    if field.field_type == FieldDefinition.TYPE_DATETIME:
        payload = fv.value_json or {}
        text = payload.get("value", "")
        if not text:
            return "—"
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return text
    if field.field_type == FieldDefinition.TYPE_BOOLEAN:
        if fv.value_boolean is None:
            return "—"
        return "Sí" if fv.value_boolean else "No"
    return "—"


def form_field_rows(fields, posted: dict, errors: dict | None = None):
    errors = errors or {}
    rows = []
    for field in fields:
        name = _field_input_name(field)
        raw_value = posted.get(name, "")
        if field.field_type == FieldDefinition.TYPE_BOOLEAN:
            checked = bool(raw_value)
            display_value = ""
        else:
            checked = False
            display_value = "" if raw_value in (None, "") else str(raw_value)
        rows.append(
            {
                "field": field,
                "input_name": name,
                "value": display_value,
                "checked": checked,
                "field_errors": errors.get(name, []),
                "choices": field.options.get("choices") or [],
                "is_full": field.field_type == FieldDefinition.TYPE_TEXT_LONG,
            }
        )
    return rows


def record_label(record: Record, fields, values_by_field: dict) -> str:
    for field in fields:
        if field.field_type in FieldDefinition.TEXT_TYPES:
            fv = values_by_field.get(field.id)
            if fv and fv.value_text:
                return fv.value_text
    return str(record.id)[:8]


def validate_record_data(fields, posted: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field in fields:
        name = _field_input_name(field)
        raw = posted.get(name, "")
        if field.field_type == FieldDefinition.TYPE_BOOLEAN:
            raw = posted.get(name, False)
        ok, message = validate_value(
            field,
            raw if raw not in ("", False) or field.required else None,
        )
        if not ok and message:
            errors.setdefault(name, []).append(message)
    return errors


def _save_field_values(record: Record, fields, posted: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field in fields:
        name = _field_input_name(field)
        raw = posted.get(name, "")
        if field.field_type == FieldDefinition.TYPE_BOOLEAN:
            raw = posted.get(name, False)
        ok, message = validate_value(field, raw if raw not in ("", False) or field.required else None)
        if not ok:
            if message:
                errors.setdefault(name, []).append(message)
            continue
        try:
            stored = _normalize_for_storage(field, raw)
        except (ValueError, InvalidOperation, TypeError):
            errors.setdefault(name, []).append("Valor no válido para este campo.")
            continue
        fv, _ = FieldValue.objects.get_or_create(record=record, field=field)
        _apply_storage(fv, field, stored)
        fv.save()
    return errors


def list_with_stats(project, *, include_deleted: bool = False):
    fields = list(active_fields(project))
    qs = Record.objects.filter(project=project).select_related("created_by", "updated_by")
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    qs = qs.prefetch_related(
        Prefetch(
            "field_values",
            queryset=FieldValue.objects.select_related("field"),
        ),
    ).order_by("-updated_at")

    records = list(qs)
    today = timezone.localdate()
    stats = {
        "total": Record.objects.filter(project=project).count(),
        "active": Record.objects.filter(project=project, is_deleted=False).count(),
        "created_today": Record.objects.filter(
            project=project,
            is_deleted=False,
            created_at__date=today,
        ).count(),
        "column_count": len(fields),
    }

    filter_field = next(
        (field for field in fields if field.field_type == FieldDefinition.TYPE_SELECT),
        None,
    )
    filter_choices = []
    if filter_field:
        filter_choices = filter_field.options.get("choices") or []

    rows = []
    for record in records:
        values_by_field = {fv.field_id: fv for fv in record.field_values.all()}
        cells = [
            {
                "field": field,
                "display": display_value(field, values_by_field.get(field.id)),
                "filter_value": _filter_value(field, values_by_field.get(field.id)),
            }
            for field in fields
        ]
        rows.append(
            {
                "record": record,
                "cells": cells,
                "label": record_label(record, fields, values_by_field),
                "filter_value": _filter_value(
                    filter_field,
                    values_by_field.get(filter_field.id),
                ) if filter_field else "",
            }
        )

    return rows, stats, fields, filter_field, filter_choices


def _filter_value(field: FieldDefinition, fv: FieldValue | None) -> str:
    if field.field_type != FieldDefinition.TYPE_SELECT or fv is None:
        return ""
    return fv.value_text or ""


def create_record(user, project, posted: dict) -> OperationResult:
    if not user_can_edit_records(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para crear registros en este proyecto.",
        )

    fields = list(active_fields(project))
    if not fields:
        return OperationResult.failure(
            "no_schema",
            "El proyecto no tiene campos activos. Defina el esquema antes de cargar datos.",
        )

    errors = validate_record_data(fields, posted)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    save_errors: dict[str, list[str]] = {}
    try:
        with transaction.atomic():
            record = Record.objects.create(
                project=project,
                created_by=user,
                updated_by=user,
            )
            save_errors = _save_field_values(record, fields, posted)
            if save_errors:
                raise ValueError("validation")
    except ValueError:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=save_errors,
        )
    except Exception:
        logger.exception("create_record unexpected project=%s", project.pk)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Registro creado correctamente.",
        payload={"record": record},
    )


def update_record(user, project, record: Record, posted: dict) -> OperationResult:
    if not user_can_edit_records(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar registros en este proyecto.",
        )
    if record.project_id != project.id or record.is_deleted:
        return OperationResult.failure("not_found", "Registro no encontrado.")

    fields = list(active_fields(project))
    errors = validate_record_data(fields, posted)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    save_errors: dict[str, list[str]] = {}
    try:
        with transaction.atomic():
            record.updated_by = user
            record.save(update_fields=["updated_by", "updated_at"])
            save_errors = _save_field_values(record, fields, posted)
            if save_errors:
                raise ValueError("validation")
    except ValueError:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=save_errors,
        )
    except Exception:
        logger.exception("update_record unexpected record=%s", record.pk)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Registro actualizado correctamente.",
        payload={"record": record},
    )


def soft_delete_record(user, project, record_id: str) -> OperationResult:
    if not user_can_edit_records(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para eliminar registros en este proyecto.",
        )

    record = get_record_for_project(project, record_id)
    if record is None:
        return OperationResult.failure("not_found", "Registro no encontrado.")

    record.is_deleted = True
    record.updated_by = user
    record.save(update_fields=["is_deleted", "updated_by", "updated_at"])
    return OperationResult.success(
        user_message="Registro eliminado correctamente.",
    )


def get_detail_rows(record: Record, fields):
    values_by_field = {fv.field_id: fv for fv in record.field_values.select_related("field")}
    rows = []
    for field in fields:
        fv = values_by_field.get(field.id)
        rows.append(
            {
                "field": field,
                "display": display_value(field, fv),
                "is_full": field.field_type == FieldDefinition.TYPE_TEXT_LONG,
            }
        )
    return rows
