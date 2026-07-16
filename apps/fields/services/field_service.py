import logging
import re

from django.apps import apps as django_apps
from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.core.services.operation_result import OperationResult
from apps.fields.models import FieldDefinition
from apps.projects.services import project_service

logger = logging.getLogger(__name__)

KEY_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")

FIELD_TYPE_LABELS = dict(FieldDefinition.FIELD_TYPE_CHOICES)


def _optional_model(app_label: str, model_name: str):
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None


def user_can_design(user, project) -> bool:
    return project_service.user_can_manage_members(user, project)


def get_design_context(user, slug: str):
    """Proyecto accesible solo si el usuario es PA (permiso design)."""
    project = project_service.get_project_for_user(user, slug)
    if project is None:
        return None, None
    if not user_can_design(user, project):
        return project, None
    return project, project_service.get_membership(user, project)


def queryset_for_project(project):
    return FieldDefinition.objects.filter(project=project).order_by("sort_order", "label")


def list_with_stats(project):
    fields = list(queryset_for_project(project))
    type_codes = {field.field_type for field in fields}
    stats = {
        "total": len(fields),
        "active": sum(1 for field in fields if field.is_active),
        "required": sum(1 for field in fields if field.required),
        "type_count": len(type_codes),
    }
    rows = [
        {
            "field": field,
            "validation_hint": validation_hint(field),
            "type_css_class": type_css_class(field.field_type),
        }
        for field in fields
    ]
    return rows, stats


def type_css_class(field_type: str) -> str:
    if field_type in FieldDefinition.NUMBER_TYPES:
        return "field-type--number"
    if field_type in {FieldDefinition.TYPE_DATE, FieldDefinition.TYPE_DATETIME}:
        return "field-type--date"
    if field_type == FieldDefinition.TYPE_SELECT:
        return "field-type--select"
    return ""


def validation_hint(field: FieldDefinition) -> str:
    if field.field_type in FieldDefinition.TEXT_TYPES:
        max_len = field.max_length or FieldDefinition.DEFAULT_MAX_LENGTH.get(field.field_type, 255)
        return f"máx. {max_len}"
    if field.field_type in FieldDefinition.NUMBER_TYPES:
        parts = []
        min_value = field.options.get("min")
        max_value = field.options.get("max")
        if min_value is not None or max_value is not None:
            parts.append(f"{min_value if min_value is not None else '—'} – {max_value if max_value is not None else '—'}")
        if field.field_type == FieldDefinition.TYPE_DECIMAL:
            places = field.options.get("decimal_places")
            if places is not None:
                parts.append(f"{places} decimales")
        return " · ".join(parts) if parts else "—"
    if field.field_type == FieldDefinition.TYPE_SELECT:
        choices = field.options.get("choices") or []
        count = len(choices)
        return f"{count} opción{'es' if count != 1 else ''}" if count else "—"
    return "—"


def field_has_values(field: FieldDefinition) -> bool:
    FieldValue = _optional_model("records", "FieldValue")
    if FieldValue is None:
        return False
    return FieldValue.objects.filter(field=field).exists()


def next_sort_order(project) -> int:
    current = FieldDefinition.objects.filter(project=project).aggregate(
        max_order=Max("sort_order"),
    )["max_order"]
    if current is None:
        return 1
    return current + 1


def default_posted(field: FieldDefinition | None = None, project=None) -> dict:
    if field is None:
        sort_order = next_sort_order(project) if project else 1
        return {
            "key": "",
            "label": "",
            "sort_order": sort_order,
            "required": False,
            "field_type": "",
            "max_length": "",
            "min_value": "",
            "max_value": "",
            "decimal_places": "",
            "select_options": "",
        }
    choices = field.options.get("choices") or []
    return {
        "key": field.key,
        "label": field.label,
        "sort_order": field.sort_order,
        "required": field.required,
        "field_type": field.field_type,
        "max_length": field.max_length or "",
        "min_value": field.options.get("min", ""),
        "max_value": field.options.get("max", ""),
        "decimal_places": field.options.get("decimal_places", ""),
        "select_options": "\n".join(choices),
    }


def posted_from_request(post) -> dict:
    return {
        "key": post.get("key", "").strip().lower(),
        "label": post.get("label", "").strip(),
        "sort_order": post.get("sort_order", "").strip(),
        "required": post.get("required") == "1",
        "field_type": post.get("field_type", "").strip(),
        "max_length": post.get("max_length", "").strip(),
        "min_value": post.get("min_value", "").strip(),
        "max_value": post.get("max_value", "").strip(),
        "decimal_places": post.get("decimal_places", "").strip(),
        "select_options": post.get("select_options", "").strip(),
    }


def _parse_optional_int(value: str, field_name: str, errors: dict, *, minimum=None, maximum=None):
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        errors.setdefault(field_name, []).append("Ingrese un número entero válido.")
        return None
    if minimum is not None and parsed < minimum:
        errors.setdefault(field_name, []).append(f"Mínimo {minimum}.")
    if maximum is not None and parsed > maximum:
        errors.setdefault(field_name, []).append(f"Máximo {maximum}.")
    return parsed


def _parse_optional_number(value: str, field_name: str, errors: dict):
    if not value:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        errors.setdefault(field_name, []).append("Ingrese un número válido.")
        return None


def _build_options(data: dict, field_type: str, errors: dict) -> dict:
    options: dict = {}
    if field_type in FieldDefinition.NUMBER_TYPES:
        min_value = _parse_optional_number(data.get("min_value", ""), "min_value", errors)
        max_value = _parse_optional_number(data.get("max_value", ""), "max_value", errors)
        if min_value is not None:
            options["min"] = min_value
        if max_value is not None:
            options["max"] = max_value
        if field_type == FieldDefinition.TYPE_DECIMAL:
            places = _parse_optional_int(
                data.get("decimal_places", ""),
                "decimal_places",
                errors,
                minimum=0,
                maximum=6,
            )
            if places is not None:
                options["decimal_places"] = places
    if field_type == FieldDefinition.TYPE_SELECT:
        raw = data.get("select_options", "")
        choices = [line.strip() for line in raw.splitlines() if line.strip()]
        if not choices:
            errors.setdefault("select_options", []).append("Ingrese al menos una opción.")
        else:
            options["choices"] = choices
    return options


def validate_field_data(
    data: dict,
    project,
    field: FieldDefinition | None = None,
    *,
    allow_key_change: bool = True,
) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    field_type = data.get("field_type", "").strip()
    valid_types = dict(FieldDefinition.FIELD_TYPE_CHOICES)

    key = data.get("key", "").strip().lower()
    if not allow_key_change and field is not None:
        key = field.key
    elif not key:
        errors.setdefault("key", []).append("Ingrese la clave interna.")
    elif len(key) > 100:
        errors.setdefault("key", []).append("Máximo 100 caracteres.")
    elif not KEY_RE.match(key):
        errors.setdefault("key", []).append(
            "Use solo letras minúsculas, números, guiones o guiones bajos."
        )
    else:
        qs = FieldDefinition.objects.filter(project=project, key=key)
        if field is not None:
            qs = qs.exclude(pk=field.pk)
        if qs.exists():
            errors.setdefault("key", []).append("Ya existe un campo con esta clave en el proyecto.")

    label = data.get("label", "").strip()
    if not label:
        errors.setdefault("label", []).append("Ingrese la etiqueta visible.")
    elif len(label) > 200:
        errors.setdefault("label", []).append("Máximo 200 caracteres.")

    sort_order = _parse_optional_int(
        str(data.get("sort_order", "")),
        "sort_order",
        errors,
        minimum=0,
    )
    if sort_order is None and "sort_order" not in errors:
        errors.setdefault("sort_order", []).append("Ingrese el orden.")

    if field_type not in valid_types:
        errors.setdefault("field_type", []).append("Seleccione un tipo de campo.")

    max_length = None
    if field_type in FieldDefinition.TEXT_TYPES:
        max_length = _parse_optional_int(
            data.get("max_length", ""),
            "max_length",
            errors,
            minimum=1,
            maximum=10000,
        )

    options: dict = {}
    if field_type and field_type in valid_types and not errors.get("field_type"):
        options = _build_options(data, field_type, errors)

    if field is not None and field_type and field_type != field.field_type:
        if field_has_values(field):
            errors.setdefault("field_type", []).append(
                "No puede cambiar el tipo: existen registros con datos en este campo."
            )

    data["_validated"] = {
        "key": key,
        "label": label,
        "sort_order": sort_order,
        "required": bool(data.get("required")),
        "field_type": field_type,
        "max_length": max_length,
        "options": options,
    }
    return errors


def create_field(user, project, data: dict) -> OperationResult:
    if not user_can_design(user, project):
        return OperationResult.failure(
            "forbidden",
            "Solo el administrador del proyecto (PA) puede diseñar campos.",
        )

    errors = validate_field_data(data, project)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    validated = data["_validated"]
    try:
        with transaction.atomic():
            field = FieldDefinition.objects.create(
                project=project,
                key=validated["key"],
                label=validated["label"],
                field_type=validated["field_type"],
                options=validated["options"],
                max_length=validated["max_length"],
                required=validated["required"],
                sort_order=validated["sort_order"],
            )
    except IntegrityError:
        logger.exception("create_field IntegrityError key=%s", validated.get("key"))
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"key": ["Ya existe un campo con esta clave en el proyecto."]},
        )
    except Exception:
        logger.exception("create_field unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Campo creado correctamente.",
        payload={"field": field},
    )


def update_field(user, project, field: FieldDefinition, data: dict) -> OperationResult:
    if not user_can_design(user, project):
        return OperationResult.failure(
            "forbidden",
            "Solo el administrador del proyecto (PA) puede modificar campos.",
        )

    if field.project_id != project.id:
        return OperationResult.failure("not_found", "Campo no encontrado.")

    allow_key_change = not field_has_values(field)
    errors = validate_field_data(
        data,
        project,
        field=field,
        allow_key_change=allow_key_change,
    )
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo guardar.",
            errors=errors,
        )

    validated = data["_validated"]
    type_changed = validated["field_type"] != field.field_type

    try:
        field.key = validated["key"] if allow_key_change else field.key
        field.label = validated["label"]
        field.field_type = validated["field_type"]
        field.options = validated["options"]
        field.max_length = validated["max_length"]
        field.required = validated["required"]
        field.sort_order = validated["sort_order"]
        if type_changed:
            field.version += 1
        field.save()
    except IntegrityError:
        return OperationResult.failure(
            "duplicate",
            "Revise los datos marcados; no se pudo guardar.",
            errors={"key": ["Ya existe un campo con esta clave en el proyecto."]},
        )
    except Exception:
        logger.exception("update_field unexpected")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Campo actualizado correctamente.",
        payload={"field": field},
    )


def set_field_active(user, project, field_id: str, *, active: bool) -> OperationResult:
    if not user_can_design(user, project):
        return OperationResult.failure(
            "forbidden",
            "Solo el administrador del proyecto (PA) puede modificar campos.",
        )

    try:
        field = FieldDefinition.objects.get(pk=field_id, project=project)
    except (FieldDefinition.DoesNotExist, ValueError):
        return OperationResult.failure("not_found", "Campo no encontrado.")

    if not active and field_has_values(field):
        field.is_active = False
        field.save(update_fields=["is_active", "updated_at"])
        return OperationResult.success(
            user_message=f"Campo «{field.label}» desactivado. Los datos existentes se conservan.",
        )

    field.is_active = active
    field.save(update_fields=["is_active", "updated_at"])
    if active:
        return OperationResult.success(
            user_message=f"Campo «{field.label}» reactivado.",
        )
    return OperationResult.success(
        user_message=f"Campo «{field.label}» desactivado.",
    )
