"""Normalización de campos SourceProfile (source_definition.md)."""

DATE_CONTENT_TYPES = frozenset({"date", "datetime"})


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_txt_fixed_bounds(field: dict) -> dict:
    """
    Resuelve start/end/length/char para txt_fixed.

    Alternativas del doc:
    - start + end
    - start + length  → end = start + length - 1
    - char (marcador) ± start/length opcionales
    """
    item = dict(field or {})
    start = _to_int(item.get("start"))
    end = _to_int(item.get("end"))
    length = _to_int(item.get("length"))
    char = item.get("char")
    if isinstance(char, str):
        char = char.strip()
    else:
        char = "" if char in (None, "") else str(char)

    if start is not None and length is not None and length >= 1:
        end = start + length - 1
    elif start is not None and end is not None and end >= start:
        length = end - start + 1
    elif start is not None and end is None and not char:
        end = start
        length = 1
    elif char and start is not None and end is None and length is None:
        end = start
        length = 1
    elif char and start is None and length is not None and length >= 1:
        # Marcador sin posición fija: no hay rango numérico para solapes
        pass

    result: dict = {}
    if start is not None:
        result["start"] = start
    if end is not None:
        result["end"] = end
    if length is not None:
        result["length"] = length
    if char:
        result["char"] = char
    return result


def build_source_meta(field: dict, file_type_code: str) -> dict:
    code = (file_type_code or "").strip()
    meta: dict = {}

    if code == "txt_fixed":
        bounds = resolve_txt_fixed_bounds(field)
        for key in ("start", "end", "length", "char"):
            if key in bounds:
                meta[key] = bounds[key]
        return meta

    if code in ("txt_delimited", "csv"):
        if field.get("column_index") is not None:
            meta["column_index"] = field["column_index"]
        source_column = (field.get("source_column") or "").strip()
        if source_column:
            meta["source_column"] = source_column
        return meta

    if code == "xlsx":
        column = (field.get("column") or "").strip()
        if column:
            meta["column"] = column.upper()
        return meta

    if code == "json":
        json_path = (field.get("json_path") or "").strip()
        if json_path:
            meta["json_path"] = json_path
        return meta

    if code == "xml":
        element = (field.get("element") or "").strip()
        if element:
            meta["element"] = element
        return meta

    return meta


def flatten_field_for_edit(field: dict) -> dict:
    """Expone claves planas para el editor a partir de source_meta guardado."""
    item = dict(field or {})
    meta = item.get("source_meta") or {}

    for key in ("start", "end", "length", "char", "column_index", "source_column", "column", "json_path", "element"):
        if key not in item or item[key] in (None, ""):
            if key in meta and meta[key] not in (None, ""):
                item[key] = meta[key]

    if item.get("column"):
        item["column"] = str(item["column"]).upper()

    if (item.get("file_type_code") or "").strip() == "txt_fixed" or (
        "start" in item or "end" in item or "length" in item or "char" in item
    ):
        bounds = resolve_txt_fixed_bounds(item)
        item.update(bounds)

    return item


def normalize_field(field: dict, file_type_code: str) -> dict:
    item = flatten_field_for_edit(field)
    name = (item.get("name") or "").strip().lower()
    normalized = {
        "name": name,
        "label": (item.get("label") or "").strip(),
        "content_type": (item.get("content_type") or "").strip(),
        "required": bool(item.get("required")),
    }

    pattern = (item.get("pattern") or "").strip()
    if pattern:
        normalized["pattern"] = pattern

    date_format = (item.get("date_format") or "").strip()
    if date_format:
        normalized["date_format"] = date_format

    code = (file_type_code or "").strip()
    if code == "txt_fixed":
        bounds = resolve_txt_fixed_bounds(item)
        normalized.update(bounds)
        # Compat editor: si hay rango numérico incompleto y no hay char, aplicar defaults
        if "char" not in normalized and "start" not in normalized:
            normalized["start"] = 1
            normalized["end"] = 1
            normalized["length"] = 1
        elif "start" in normalized and "end" not in normalized and "char" not in normalized:
            normalized["end"] = normalized["start"]
            normalized["length"] = 1
    elif code in ("txt_delimited", "csv"):
        normalized["column_index"] = int(item.get("column_index") or 0)
        source_column = (item.get("source_column") or "").strip()
        if source_column:
            normalized["source_column"] = source_column
    elif code == "xlsx":
        normalized["column"] = (item.get("column") or "").strip().upper()
    elif code == "json":
        normalized["json_path"] = (item.get("json_path") or normalized["name"]).strip()
    elif code == "xml":
        normalized["element"] = (item.get("element") or normalized["name"]).strip()

    normalized["source_meta"] = build_source_meta(normalized, code)
    return normalized


def normalize_fields_list(fields: list, file_type_code: str) -> list:
    return [normalize_field(field, file_type_code) for field in (fields or [])]
