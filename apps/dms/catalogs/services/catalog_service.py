import json
import re
from typing import Any

from django.db import models as dj_models

from apps.core.services.operation_result import OperationResult
from apps.dms.catalogs.catalog_registry import CATALOGS, CatalogDef, get_catalog

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def default_posted(catalog: CatalogDef) -> dict[str, Any]:
    posted: dict[str, Any] = {"sort_order": "0", "is_active": True}
    model_fields = {f.name for f in catalog.model._meta.get_fields()}
    for field_def in catalog.form_fields:
        if field_def.field_type == "checkbox":
            posted[field_def.name] = True
        elif field_def.field_type == "integer":
            posted[field_def.name] = "0"
        elif field_def.field_type == "json":
            posted[field_def.name] = "[]" if field_def.name.endswith("s") else ""
        else:
            posted[field_def.name] = ""
    for name in model_fields:
        if name not in posted and name not in ("id", "created_at", "updated_at"):
            posted.setdefault(name, "")
    return posted


def posted_from_request(catalog: CatalogDef, post_data) -> dict[str, Any]:
    posted = default_posted(catalog)
    checkbox_fields = {
        field_def.name
        for field_def in catalog.form_fields
        if field_def.field_type == "checkbox"
    }
    model_fields = {f.name for f in catalog.model._meta.get_fields()}
    for name in model_fields:
        if name in ("id", "created_at", "updated_at"):
            continue
        if name in checkbox_fields or name in (
            "is_auto_detect",
            "allows_custom_value",
            "requires_date_format",
            "allows_custom_pattern",
            "requires_format",
            "supports_format",
            "is_active",
        ):
            posted[name] = post_data.get(name) == "1" or post_data.get(name) == "on"
        elif name in post_data:
            posted[name] = (post_data.get(name) or "").strip()
    return posted


def instance_to_posted(catalog: CatalogDef, instance) -> dict[str, Any]:
    posted: dict[str, Any] = {}
    for field_def in catalog.form_fields:
        value = getattr(instance, field_def.name, "")
        if field_def.field_type == "checkbox":
            posted[field_def.name] = bool(value)
        elif field_def.field_type == "json":
            if value in (None, ""):
                posted[field_def.name] = ""
            else:
                posted[field_def.name] = json.dumps(value, ensure_ascii=False, indent=2)
        elif field_def.field_type == "integer":
            posted[field_def.name] = str(value)
        else:
            posted[field_def.name] = value or ""
    return posted


def display_value(instance, field_name: str) -> str:
    value = getattr(instance, field_name, "")
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (list, dict)):
        if not value:
            return "—"
        return json.dumps(value, ensure_ascii=False)
    if value in (None, ""):
        return "—"
    return str(value)


def _parse_json_field(raw: str, field_name: str, errors: dict, required: bool) -> Any:
    if not raw:
        if required:
            errors.setdefault(field_name, []).append("Este campo es obligatorio.")
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        errors.setdefault(field_name, []).append("JSON no válido.")
        return None


def _validate_posted(catalog: CatalogDef, posted: dict, is_edit: bool) -> tuple[dict, dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    cleaned: dict[str, Any] = {}

    model_field_names = {
        f.name
        for f in catalog.model._meta.get_fields()
        if f.name not in ("id", "created_at", "updated_at")
    }
    boolean_fields = {
        f.name
        for f in catalog.model._meta.get_fields()
        if getattr(f, "get_internal_type", lambda: "")() == "BooleanField"
    }
    integer_fields = {
        f.name
        for f in catalog.model._meta.get_fields()
        if getattr(f, "get_internal_type", lambda: "")() in ("IntegerField", "PositiveIntegerField")
    }
    json_fields = {
        f.name
        for f in catalog.model._meta.get_fields()
        if getattr(f, "get_internal_type", lambda: "")() == "JSONField"
    }

    readonly_on_edit = {f.name for f in catalog.form_fields if f.readonly_on_edit}

    for name in model_field_names:
        if is_edit and name in readonly_on_edit:
            continue

        raw = posted.get(name)

        if name in boolean_fields:
            cleaned[name] = bool(raw)
            continue

        if name in integer_fields:
            text = str(raw or "").strip()
            if not text and name == "sort_order":
                cleaned[name] = 0
                continue
            try:
                cleaned[name] = int(text or "0")
            except ValueError:
                errors.setdefault(name, []).append("Debe ser un número entero.")
            continue

        if name in json_fields:
            text = str(raw or "").strip()
            if not text:
                cleaned[name] = None if name == "config_schema" or name == "param_schema" else []
                continue
            parsed = _parse_json_field(text, name, errors, required=False)
            if name not in errors:
                cleaned[name] = parsed
            continue

        text = str(raw or "").strip()
        if name == "name" and not text:
            errors.setdefault(name, []).append("Este campo es obligatorio.")
            continue
        if name == "code" and not is_edit and not text:
            errors.setdefault(name, []).append("Este campo es obligatorio.")
            continue
        if name in ("parser_key", "serializer_key", "syntax", "resolver_key") and not text:
            errors.setdefault(name, []).append("Este campo es obligatorio.")
            continue
        cleaned[name] = text

    code = cleaned.get("code") or posted.get("code", "")
    if not is_edit and code:
        code_text = str(code)
        if catalog.slug == "execution-error-codes":
            if not ERROR_CODE_RE.match(code_text):
                errors.setdefault("code", []).append(
                    "Use mayúsculas, números y guiones bajos (ej. CONTENT_TYPE_MISMATCH)."
                )
        elif not SLUG_RE.match(code_text.lower()):
            errors.setdefault("code", []).append(
                "Use solo minúsculas, números, guiones y guiones bajos."
            )
        else:
            cleaned["code"] = code_text.lower()

    if catalog.slug == "charset-encodings":
        is_auto = cleaned.get("is_auto_detect", False)
        charset = cleaned.get("charset_value", "")
        if is_auto and charset:
            errors.setdefault("charset_value", []).append(
                "Deje vacío el valor codec si usa detección automática."
            )
        if not is_auto and not charset:
            errors.setdefault("charset_value", []).append(
                "Indique el valor codec o active detección automática."
            )

    if catalog.slug == "line-endings":
        is_auto = cleaned.get("is_auto_detect", False)
        allows_custom = cleaned.get("allows_custom_value", False)
        sequence = cleaned.get("sequence", "")
        if is_auto and sequence:
            errors.setdefault("sequence", []).append(
                "Deje vacía la secuencia si usa detección automática."
            )
        if not is_auto and not allows_custom and not sequence:
            errors.setdefault("sequence", []).append(
                "Indique la secuencia, active custom o detección automática."
            )

    return cleaned, errors


def _validate_unique_auto_detect(catalog: CatalogDef, instance, cleaned: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    if catalog.slug not in ("charset-encodings", "line-endings"):
        return errors
    if not cleaned.get("is_auto_detect"):
        return errors

    field = "is_auto_detect"
    qs = catalog.model.objects.filter(is_auto_detect=True)
    if instance is not None:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        errors.setdefault(field, []).append(
            "Ya existe un registro con detección automática activa."
        )
    return errors


def create_catalog_item(catalog_slug: str, posted: dict) -> OperationResult:
    catalog = get_catalog(catalog_slug)
    cleaned, errors = _validate_posted(catalog, posted, is_edit=False)
    errors.update(_validate_unique_auto_detect(catalog, None, cleaned))
    if errors:
        return OperationResult.failure(
            "validation",
            "Revise los campos marcados.",
            errors=errors,
        )

    if catalog.model.objects.filter(code=cleaned["code"]).exists():
        return OperationResult.failure(
            "duplicate",
            "Ya existe un registro con ese código.",
            errors={"code": ["Código duplicado."]},
        )

    instance = catalog.model()
    for key, value in cleaned.items():
        setattr(instance, key, value)
    instance.save()
    if catalog_slug == "execution-error-codes":
        from apps.dms.transform_execution.services.execution_error_catalog_service import (
            invalidate_cache,
        )

        invalidate_cache()
    return OperationResult.success(
        user_message="Registro creado correctamente.",
        item=instance,
    )


def update_catalog_item(catalog_slug: str, instance, posted: dict) -> OperationResult:
    catalog = get_catalog(catalog_slug)
    cleaned, errors = _validate_posted(catalog, posted, is_edit=True)
    errors.update(_validate_unique_auto_detect(catalog, instance, cleaned))
    if errors:
        return OperationResult.failure(
            "validation",
            "Revise los campos marcados.",
            errors=errors,
        )

    for key, value in cleaned.items():
        setattr(instance, key, value)
    instance.save()
    if catalog_slug == "execution-error-codes":
        from apps.dms.transform_execution.services.execution_error_catalog_service import (
            invalidate_cache,
        )

        invalidate_cache()
    return OperationResult.success(
        user_message="Registro actualizado correctamente.",
        item=instance,
    )


def deactivate_catalog_item(catalog_slug: str, instance) -> OperationResult:
    if not instance.is_active:
        return OperationResult.failure(
            "inactive",
            "El registro ya está inactivo.",
        )
    instance.is_active = False
    instance.save(update_fields=["is_active", "updated_at"])
    if catalog_slug == "execution-error-codes":
        from apps.dms.transform_execution.services.execution_error_catalog_service import (
            invalidate_cache,
        )

        invalidate_cache()
    return OperationResult.success(user_message="Registro desactivado.")


def list_items(catalog_slug: str):
    catalog = get_catalog(catalog_slug)
    return catalog.model.objects.all()


def get_item(catalog_slug: str, pk):
    catalog = get_catalog(catalog_slug)
    return catalog.model.objects.get(pk=pk)


def hub_stats() -> dict[str, int]:
    return {slug: catalog.model.objects.count() for slug, catalog in CATALOGS.items()}
