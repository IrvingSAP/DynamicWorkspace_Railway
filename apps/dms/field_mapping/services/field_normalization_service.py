"""Normalización de FieldMapping (field_mapping.md)."""

MVP_KINDS = frozenset({"direct", "constant", "concat", "generated", "split", "expression"})
PHASE2_KINDS = frozenset()
ALL_KINDS = MVP_KINDS | PHASE2_KINDS

GENERATOR_TYPES = frozenset(
    {
        "sequence_numeric",
        "sequence_padded",
        "sequence_alphanumeric",
        "sequence_template",
        "unique_uuid",
        "unique_job_counter",
        "job_timestamp",
        "row_number",
    }
)

SPLIT_PARTS = frozenset({"first_word", "rest", "delimiter", "substring", "regex"})

EXPRESSION_OPS = frozenset(
    {"add", "subtract", "multiply", "divide", "concat", "coalesce"}
)
EXPRESSION_MAX_DEPTH = 5

TRANSFORM_OPS_MVP = frozenset(
    {"trim", "upper", "lower", "date_format", "pad_left", "pad_right", "default_if_empty"}
)


def _normalize_expression_node(node, depth: int = 0) -> dict | None:
    if not isinstance(node, dict) or depth > EXPRESSION_MAX_DEPTH:
        return None
    if "field" in node:
        name = str(node.get("field") or "").strip().lower()
        return {"field": name} if name else None
    if "literal" in node:
        return {"literal": node.get("literal")}
    op = (node.get("op") or "").strip()
    if op not in EXPRESSION_OPS:
        return None
    left = _normalize_expression_node(node.get("left"), depth + 1)
    right = _normalize_expression_node(node.get("right"), depth + 1)
    if left is None or right is None:
        return None
    return {"op": op, "left": left, "right": right}


def collect_expression_fields(node: dict | None) -> list[str]:
    if not isinstance(node, dict):
        return []
    if "field" in node:
        name = str(node.get("field") or "").strip().lower()
        return [name] if name else []
    fields: list[str] = []
    for key in ("left", "right"):
        for name in collect_expression_fields(node.get(key)):
            if name not in fields:
                fields.append(name)
    return fields


def normalize_split(raw_split: dict) -> dict:
    split = dict(raw_split or {})
    part = (split.get("part") or "").strip()
    clean: dict = {"part": part}
    if part == "delimiter":
        clean["delimiter"] = "" if split.get("delimiter") is None else str(split.get("delimiter"))
        try:
            clean["index"] = int(split.get("index") or 0)
        except (TypeError, ValueError):
            clean["index"] = 0
    elif part == "substring":
        try:
            clean["start"] = int(split.get("start") or 0)
        except (TypeError, ValueError):
            clean["start"] = 0
        try:
            clean["length"] = int(split.get("length") or 0)
        except (TypeError, ValueError):
            clean["length"] = 0
    elif part == "regex":
        clean["pattern"] = str(split.get("pattern") or "")
        try:
            clean["group"] = int(split.get("group") or 0)
        except (TypeError, ValueError):
            clean["group"] = 0
    return clean


def normalize_mapping(item: dict) -> dict:
    raw = dict(item or {})
    kind = (raw.get("mapping_kind") or "direct").strip()
    target = (raw.get("target_field") or "").strip().lower()
    source_fields = [
        str(name).strip().lower()
        for name in (raw.get("source_fields") or [])
        if str(name).strip()
    ]
    pipeline = []
    for step in raw.get("transform_pipeline") or []:
        if not isinstance(step, dict):
            continue
        op = (step.get("op") or "").strip()
        if not op:
            continue
        entry = {"op": op}
        for key in ("format", "char", "length", "value", "map"):
            if key in step and step[key] not in (None, ""):
                entry[key] = step[key]
        formats = step.get("input_formats")
        if isinstance(formats, list):
            cleaned = [str(item).strip() for item in formats if str(item).strip()]
            if cleaned:
                entry["input_formats"] = cleaned
        pipeline.append(entry)

    try:
        sort_order = int(raw.get("sort_order") or 0)
    except (TypeError, ValueError):
        sort_order = 0

    normalized = {
        "target_field": target,
        "mapping_kind": kind,
        "source_fields": source_fields,
        "transform_pipeline": pipeline,
        "sort_order": sort_order,
        "is_active": bool(raw.get("is_active", True)),
    }

    if kind == "constant":
        normalized["value"] = "" if raw.get("value") is None else str(raw.get("value"))
        normalized["source_fields"] = []
    elif kind == "concat":
        parts = []
        for part in raw.get("parts") or []:
            if not isinstance(part, dict):
                continue
            ptype = (part.get("type") or "").strip()
            if ptype == "literal":
                parts.append({"type": "literal", "value": str(part.get("value") or "")})
            elif ptype == "field":
                name = (part.get("name") or "").strip().lower()
                if name:
                    parts.append({"type": "field", "name": name})
                    if name not in normalized["source_fields"]:
                        normalized["source_fields"].append(name)
        normalized["parts"] = parts
    elif kind == "generated":
        generator = dict(raw.get("generator") or {})
        gtype = (generator.get("type") or "").strip()
        clean = {"type": gtype}
        for key in (
            "start",
            "step",
            "prefix",
            "suffix",
            "pad_length",
            "pad_char",
            "reset_per_job",
            "template",
            "scope",
        ):
            if key in generator and generator[key] not in (None, ""):
                clean[key] = generator[key]
        if "reset_per_job" not in clean:
            clean["reset_per_job"] = True
        if "start" not in clean and gtype.startswith("sequence"):
            clean["start"] = 1
        if "step" not in clean and gtype.startswith("sequence"):
            clean["step"] = 1
        normalized["generator"] = clean
        normalized["source_fields"] = []
    elif kind == "split":
        normalized["split"] = normalize_split(raw.get("split") or {})
        if len(normalized["source_fields"]) > 1:
            normalized["source_fields"] = normalized["source_fields"][:1]
    elif kind == "expression":
        expression = _normalize_expression_node(raw.get("expression") or {})
        normalized["expression"] = expression or {}
        fields = collect_expression_fields(normalized["expression"])
        normalized["source_fields"] = fields

    return normalized


def normalize_mappings_list(mappings: list) -> list:
    result = [normalize_mapping(item) for item in (mappings or [])]
    result.sort(key=lambda item: (item.get("sort_order") or 0, item.get("target_field") or ""))
    return result
