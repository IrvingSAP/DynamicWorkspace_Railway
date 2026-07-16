"""Tema visual de record_expand por proyecto — ver records_datatables_design.md."""

from __future__ import annotations

from typing import Any

from apps.core.services.operation_result import OperationResult
from apps.fields.models import FieldDefinition
from apps.projects.models import ProjectRecordsExpandTheme

BOOLEAN_FIELD_OPTIONS = [
    ("grid_cell_border", "cell-border", "Bordes en celdas"),
    ("layout_compact", "compact", "Diseño compacto"),
    ("row_stripe", "stripe", "Filas alternas"),
    ("row_hover", "hover", "Resaltar fila al pasar el mouse"),
    ("column_order_highlight", "order-column", "Resaltar columna ordenada"),
    ("cell_nowrap", "nowrap", "Sin salto de línea en celdas"),
]

COLOR_KEYS = (
    "header_bg",
    "header_color",
    "header_border",
    "cell_border",
    "stripe_bg",
    "hover_bg",
)

BOOLEAN_KEYS = tuple(code for code, _, _ in BOOLEAN_FIELD_OPTIONS)

THEME_FIELD_KEYS = COLOR_KEYS + BOOLEAN_KEYS + ("page_length",)

TECHNICAL_DEFAULTS: dict[str, Any] = {
    "header_bg": "#e8eef4",
    "header_color": "#1a1d21",
    "header_border": "#c5cdd8",
    "cell_border": "#d4d9e0",
    "stripe_bg": "#f7f9fb",
    "hover_bg": "#e8eef4",
    "grid_cell_border": True,
    "layout_compact": True,
    "row_stripe": True,
    "row_hover": True,
    "column_order_highlight": True,
    "cell_nowrap": True,
    "page_length": 25,
}


def _theme_values(theme: ProjectRecordsExpandTheme | None) -> dict[str, Any]:
    if theme is None:
        return dict(TECHNICAL_DEFAULTS)
    return {
        "header_bg": theme.header_bg,
        "header_color": theme.header_color,
        "header_border": theme.header_border,
        "cell_border": theme.cell_border,
        "stripe_bg": theme.stripe_bg,
        "hover_bg": theme.hover_bg,
        "grid_cell_border": theme.grid_cell_border,
        "layout_compact": theme.layout_compact,
        "row_stripe": theme.row_stripe,
        "row_hover": theme.row_hover,
        "column_order_highlight": theme.column_order_highlight,
        "cell_nowrap": theme.cell_nowrap,
        "page_length": theme.page_length,
    }


def _table_class_string(values: dict[str, Any]) -> str:
    classes = ["dw-datatable", "display"]
    for field_name, class_name, _ in BOOLEAN_FIELD_OPTIONS:
        if values.get(field_name):
            classes.append(class_name)
    return " ".join(classes)


def resolve_expand_theme(project) -> dict[str, Any]:
    try:
        theme = project.expand_theme
    except ProjectRecordsExpandTheme.DoesNotExist:
        theme = None

    values = _theme_values(theme)
    resolved = {
        **values,
        "has_saved_theme": theme is not None,
        "table_class_string": _table_class_string(values),
        "css_vars": {key: values[key] for key in COLOR_KEYS},
        "updated_at": theme.updated_at if theme else None,
    }
    return resolved


def resolve_expand_display(project) -> dict[str, Any]:
    """Alias de compatibilidad para templates y vistas existentes."""
    return resolve_expand_theme(project)


def column_align_class(field_type: str) -> str:
    if field_type in FieldDefinition.NUMBER_TYPES:
        return "dt-body-right"
    if field_type in {
        FieldDefinition.TYPE_DATE,
        FieldDefinition.TYPE_DATETIME,
        FieldDefinition.TYPE_BOOLEAN,
    }:
        return "dt-body-center"
    return ""


def posted_from_request(post) -> dict[str, Any]:
    data: dict[str, Any] = {
        "page_length": post.get("page_length", "").strip(),
    }
    for key in COLOR_KEYS:
        data[key] = post.get(key, "").strip()
    for key in BOOLEAN_KEYS:
        data[key] = post.get(key) == "on"
    return data


def _valid_hex_color(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def validate_theme_data(data: dict[str, Any]) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    for key in COLOR_KEYS:
        value = (data.get(key) or "").strip()
        if not value:
            errors.setdefault(key, []).append("Ingrese un color hexadecimal (#RRGGBB).")
        elif not _valid_hex_color(value):
            errors.setdefault(key, []).append("Use un color hexadecimal (#RRGGBB).")

    page_length = (data.get("page_length") or "").strip()
    if not page_length:
        errors.setdefault("page_length", []).append("Ingrese filas por página.")
    else:
        try:
            parsed = int(page_length)
        except ValueError:
            errors.setdefault("page_length", []).append("Ingrese un número entero.")
        else:
            if parsed < 10 or parsed > 100:
                errors.setdefault("page_length", []).append("Entre 10 y 100 filas por página.")

    return errors


def _theme_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in COLOR_KEYS:
        payload[key] = (data.get(key) or "").strip()
    for key in BOOLEAN_KEYS:
        payload[key] = bool(data.get(key))
    payload["page_length"] = int((data.get("page_length") or "").strip())
    return payload


def save_expand_theme(project, data: dict[str, Any]) -> OperationResult:
    errors = validate_theme_data(data)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos de apariencia.",
            errors=errors,
        )

    payload = _theme_payload(data)
    ProjectRecordsExpandTheme.objects.update_or_create(
        project=project,
        defaults=payload,
    )
    return OperationResult.success(
        user_message="Apariencia de la tabla expandida guardada correctamente.",
    )


def save_expand_display(project, data: dict[str, Any]) -> OperationResult:
    """Alias de compatibilidad."""
    return save_expand_theme(project, data)


def boolean_fields_from_posted(posted: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": field_name,
            "class_name": class_name,
            "label": label,
            "checked": bool(posted.get(field_name)),
        }
        for field_name, class_name, label in BOOLEAN_FIELD_OPTIONS
    ]


def form_context(project, posted_override: dict[str, Any] | None = None) -> dict[str, Any]:
    saved = resolve_expand_theme(project)
    posted = posted_override or {key: saved[key] for key in THEME_FIELD_KEYS}

    if posted_override:
        resolved = {
            **posted,
            "has_saved_theme": saved["has_saved_theme"],
            "table_class_string": _table_class_string(posted),
            "css_vars": {key: posted[key] for key in COLOR_KEYS},
            "updated_at": saved["updated_at"],
        }
    else:
        resolved = saved

    return {
        "posted": posted,
        "resolved": resolved,
        "boolean_field_options": BOOLEAN_FIELD_OPTIONS,
        "boolean_fields": boolean_fields_from_posted(posted),
    }
