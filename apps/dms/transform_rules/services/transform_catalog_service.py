"""Catálogo de operaciones de transformación (transform_rules.md)."""

TRANSFORM_OPS_MVP = frozenset(
    {
        "trim",
        "upper",
        "lower",
        "date_format",
        "pad_left",
        "pad_right",
        "default_if_empty",
    }
)

TRANSFORM_OPS_PHASE2 = frozenset(
    {
        "replace_map",
        "replace",
        "substring",
        "ltrim",
        "rtrim",
        "regex_extract",
        "coalesce",
        "number_format",
        "boolean_map",
    }
)

ALL_TRANSFORM_OPS = TRANSFORM_OPS_MVP | TRANSFORM_OPS_PHASE2

MAX_PIPELINE_STEPS = 20

TRANSFORM_OP_OPTIONS = [
    {"code": "trim", "name": "Trim", "phase": "mvp", "params": []},
    {"code": "upper", "name": "Mayúsculas", "phase": "mvp", "params": []},
    {"code": "lower", "name": "Minúsculas", "phase": "mvp", "params": []},
    {
        "code": "date_format",
        "name": "Formato fecha",
        "phase": "mvp",
        "params": ["format", "input_formats"],
    },
    {
        "code": "pad_left",
        "name": "Pad izquierda",
        "phase": "mvp",
        "params": ["char", "length"],
    },
    {
        "code": "pad_right",
        "name": "Pad derecha",
        "phase": "mvp",
        "params": ["char", "length"],
    },
    {
        "code": "default_if_empty",
        "name": "Default si vacío",
        "phase": "mvp",
        "params": ["value"],
    },
    {"code": "replace_map", "name": "Mapa de códigos", "phase": "phase_2", "params": ["map"]},
    {
        "code": "replace",
        "name": "Reemplazar texto",
        "phase": "phase_2",
        "params": ["find", "replace", "regex"],
    },
    {
        "code": "substring",
        "name": "Substring",
        "phase": "phase_2",
        "params": ["start", "length"],
    },
    {"code": "ltrim", "name": "Trim izquierda", "phase": "phase_2", "params": []},
    {"code": "rtrim", "name": "Trim derecha", "phase": "phase_2", "params": []},
    {
        "code": "regex_extract",
        "name": "Extraer regex",
        "phase": "phase_2",
        "params": ["pattern", "group"],
    },
    {
        "code": "coalesce",
        "name": "Coalesce",
        "phase": "phase_2",
        "params": ["value", "values"],
    },
    {
        "code": "number_format",
        "name": "Formato numérico",
        "phase": "phase_2",
        "params": ["decimal_places", "thousands_sep", "decimal_sep"],
    },
    {
        "code": "boolean_map",
        "name": "Mapa booleano",
        "phase": "phase_2",
        "params": ["true_values", "false_values", "output_true", "output_false"],
    },
]


def _params_from_schema(schema) -> list[str]:
    if isinstance(schema, list):
        return [str(item) for item in schema if str(item).strip()]
    if isinstance(schema, dict):
        props = schema.get("params") or schema.get("properties") or schema.get("fields")
        if isinstance(props, list):
            return [str(item) for item in props if str(item).strip()]
        if isinstance(props, dict):
            return list(props.keys())
    return []


def list_transform_op_options(*, active_only: bool = True) -> list[dict]:
    """Opciones UI desde catálogo BD; fallback a TRANSFORM_OP_OPTIONS."""
    try:
        from apps.dms.models import TransformOperation

        qs = TransformOperation.objects.all().order_by("sort_order", "code")
        if active_only:
            qs = qs.filter(is_active=True)
        rows = list(qs)
        if rows:
            result = []
            for row in rows:
                params = _params_from_schema(row.param_schema)
                fallback = next(
                    (item for item in TRANSFORM_OP_OPTIONS if item["code"] == row.code),
                    None,
                )
                if not params and fallback:
                    params = list(fallback.get("params") or [])
                result.append(
                    {
                        "code": row.code,
                        "name": row.name,
                        "phase": row.phase or "mvp",
                        "params": params,
                    }
                )
            return result
    except Exception:
        pass
    if active_only:
        return [dict(item) for item in TRANSFORM_OP_OPTIONS if item.get("phase") == "mvp"]
    return [dict(item) for item in TRANSFORM_OP_OPTIONS]


def active_transform_op_codes() -> frozenset[str]:
    options = list_transform_op_options(active_only=True)
    if options:
        return frozenset(item["code"] for item in options)
    return frozenset(TRANSFORM_OPS_MVP)


def normalize_pipeline_step(step: dict) -> dict | None:
    if not isinstance(step, dict):
        return None
    op = (step.get("op") or "").strip()
    if not op:
        return None
    entry: dict = {"op": op}
    for key in (
        "format",
        "char",
        "value",
        "find",
        "replace",
        "pattern",
        "thousands_sep",
        "decimal_sep",
        "output_true",
        "output_false",
    ):
        if key in step and step[key] not in (None, ""):
            entry[key] = str(step[key]) if key != "value" else (
                "" if step[key] is None else str(step[key])
            )
    if "value" in step and "value" not in entry:
        entry["value"] = "" if step["value"] is None else str(step["value"])
    if "char" in entry:
        entry["char"] = str(entry["char"])[:1]
    for key in ("length", "start", "group", "decimal_places"):
        if key in step and step[key] not in (None, ""):
            try:
                entry[key] = int(step[key])
            except (TypeError, ValueError):
                entry[key] = step[key]
    if "regex" in step:
        entry["regex"] = bool(step["regex"])
    if "map" in step and isinstance(step["map"], dict):
        entry["map"] = dict(step["map"])
    for key in ("input_formats", "values", "true_values", "false_values", "fields"):
        raw = step.get(key)
        if isinstance(raw, list):
            cleaned = [str(item).strip() for item in raw if str(item).strip() or item == 0]
            if cleaned or key in {"true_values", "false_values", "values"}:
                entry[key] = [str(item) for item in raw] if key != "input_formats" else cleaned
        elif isinstance(raw, str) and raw.strip():
            entry[key] = [part.strip() for part in raw.split(",") if part.strip()]
    formats = step.get("input_formats")
    if isinstance(formats, list) and "input_formats" not in entry:
        cleaned = [str(item).strip() for item in formats if str(item).strip()]
        if cleaned:
            entry["input_formats"] = cleaned
    elif isinstance(formats, str) and formats.strip() and "input_formats" not in entry:
        cleaned = [part.strip() for part in formats.split(",") if part.strip()]
        if cleaned:
            entry["input_formats"] = cleaned
    return entry


def normalize_pipeline(steps: list) -> list[dict]:
    result = []
    for step in steps or []:
        normalized = normalize_pipeline_step(step if isinstance(step, dict) else {})
        if normalized:
            result.append(normalized)
    return result
