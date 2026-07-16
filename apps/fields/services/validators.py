"""Validadores por tipo de campo — usados al guardar registros (apps.records)."""

from decimal import Decimal, InvalidOperation
from datetime import date, datetime

from apps.fields.models import FieldDefinition


def validate_value(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    """Retorna (ok, mensaje_error)."""
    if raw_value in (None, "") and not field.required:
        return True, None
    if raw_value in (None, "") and field.required:
        return False, "Este campo es obligatorio."

    validators = {
        FieldDefinition.TYPE_TEXT_SHORT: _validate_text,
        FieldDefinition.TYPE_TEXT_LONG: _validate_text,
        FieldDefinition.TYPE_INTEGER: _validate_integer,
        FieldDefinition.TYPE_DECIMAL: _validate_decimal,
        FieldDefinition.TYPE_DATE: _validate_date,
        FieldDefinition.TYPE_DATETIME: _validate_datetime,
        FieldDefinition.TYPE_BOOLEAN: _validate_boolean,
        FieldDefinition.TYPE_SELECT: _validate_select,
    }
    validator = validators.get(field.field_type)
    if validator is None:
        return False, "Tipo de campo no soportado."
    return validator(field, raw_value)


def _validate_text(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    text = str(raw_value)
    max_len = field.max_length or FieldDefinition.DEFAULT_MAX_LENGTH.get(
        field.field_type,
        255,
    )
    if len(text) > max_len:
        return False, f"Máximo {max_len} caracteres."
    return True, None


def _validate_integer(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return False, "Ingrese un número entero válido."
    return _validate_number_range(field, value)


def _validate_decimal(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return False, "Ingrese un número decimal válido."
    decimal_places = field.options.get("decimal_places")
    if decimal_places is not None:
        exp = Decimal("1").scaleb(-int(decimal_places))
        if value != value.quantize(exp):
            return False, f"Máximo {decimal_places} decimales."
    return _validate_number_range(field, value)


def _validate_number_range(field: FieldDefinition, value) -> tuple[bool, str | None]:
    min_value = field.options.get("min")
    max_value = field.options.get("max")
    if min_value is not None and value < min_value:
        return False, f"El valor mínimo es {min_value}."
    if max_value is not None and value > max_value:
        return False, f"El valor máximo es {max_value}."
    return True, None


def _validate_date(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    if isinstance(raw_value, date):
        return True, None
    try:
        date.fromisoformat(str(raw_value))
    except ValueError:
        return False, "Ingrese una fecha válida (aaaa-mm-dd)."
    return True, None


def _validate_datetime(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    if isinstance(raw_value, datetime):
        return True, None
    text = str(raw_value)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False, "Ingrese una fecha y hora válidas."
    return True, None


def _validate_boolean(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    if raw_value in (True, False, "true", "false", "1", "0", 1, 0):
        return True, None
    return False, "Valor booleano no válido."


def _validate_select(field: FieldDefinition, raw_value) -> tuple[bool, str | None]:
    choices = field.options.get("choices") or []
    if not choices:
        return False, "El campo no tiene opciones configuradas."
    text = str(raw_value)
    if text not in choices:
        return False, "Seleccione una opción válida."
    return True, None
