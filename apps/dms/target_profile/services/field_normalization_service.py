"""Normalización de campos TargetProfile (target_definition.md)."""


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_target_meta(field: dict, file_type_code: str) -> dict:
    code = (file_type_code or "").strip()
    meta: dict = {}

    if code == "txt_fixed":
        for key in ("start", "end", "length", "align", "pad_char"):
            if field.get(key) not in (None, ""):
                meta[key] = field[key]
        return meta

    if code in ("txt_delimited", "csv"):
        if field.get("order") is not None:
            meta["order"] = field["order"]
        if "quote" in field:
            meta["quote"] = bool(field.get("quote"))
        return meta

    if code == "xlsx":
        column = (field.get("column") or "").strip()
        if column:
            meta["column"] = column.upper()
        excel_type = (field.get("excel_type") or "").strip()
        if excel_type:
            meta["excel_type"] = excel_type
        if field.get("order") is not None:
            meta["order"] = field["order"]
        return meta

    if code in {"json", "xml"}:
        path = (field.get("path") or "").strip()
        if path:
            meta["path"] = path
        if field.get("order") is not None:
            meta["order"] = field["order"]
        return meta

    return meta


def flatten_field_for_edit(field: dict) -> dict:
    item = dict(field or {})
    meta = item.get("target_meta") or {}
    for key in (
        "start",
        "end",
        "length",
        "align",
        "pad_char",
        "order",
        "quote",
        "column",
        "excel_type",
        "path",
    ):
        if key not in item or item[key] in (None, ""):
            if key in meta and meta[key] not in (None, ""):
                item[key] = meta[key]
    if item.get("column"):
        item["column"] = str(item["column"]).upper()
    return item


def normalize_field(field: dict, file_type_code: str) -> dict:
    item = flatten_field_for_edit(field)
    name = (item.get("name") or "").strip().lower()
    order = _to_int(item.get("order"))
    normalized = {
        "name": name,
        "label": (item.get("label") or "").strip() or name,
        "data_type": (item.get("data_type") or "string").strip(),
        "required": bool(item.get("required")),
        "order": order if order is not None else 1,
    }

    max_length = _to_int(item.get("max_length"))
    if max_length is not None:
        normalized["max_length"] = max_length

    default_value = item.get("default_value")
    if default_value not in (None, ""):
        normalized["default_value"] = str(default_value)

    pattern = (item.get("pattern") or "").strip()
    if pattern:
        normalized["pattern"] = pattern

    date_format = (item.get("date_format") or "").strip()
    if date_format:
        normalized["date_format"] = date_format

    datetime_format = (item.get("datetime_format") or "").strip()
    if datetime_format:
        normalized["datetime_format"] = datetime_format

    code = (file_type_code or "").strip()
    if code == "txt_fixed":
        start = _to_int(item.get("start")) or 1
        end = _to_int(item.get("end"))
        length = _to_int(item.get("length"))
        if length is not None and length >= 1:
            end = start + length - 1
        elif end is None:
            end = start
            length = 1
        else:
            length = end - start + 1
        normalized["start"] = start
        normalized["end"] = end
        normalized["length"] = length
        normalized["align"] = (item.get("align") or "left").strip() or "left"
        pad = item.get("pad_char")
        normalized["pad_char"] = " " if pad in (None, "") else str(pad)[:1]
        if "max_length" not in normalized:
            normalized["max_length"] = length
    elif code in ("txt_delimited", "csv"):
        if "quote" in item:
            normalized["quote"] = bool(item.get("quote"))
    elif code == "xlsx":
        normalized["column"] = (item.get("column") or "").strip().upper()
        excel_type = (item.get("excel_type") or "general").strip() or "general"
        normalized["excel_type"] = excel_type
    elif code in {"json", "xml"}:
        path = (item.get("path") or name).strip()
        normalized["path"] = path or name

    field_ser = item.get("serialization")
    if isinstance(field_ser, dict) and field_ser:
        normalized["serialization"] = field_ser

    normalized["target_meta"] = build_target_meta(normalized, code)
    return normalized


def normalize_fields_list(fields: list, file_type_code: str) -> list:
    result = [normalize_field(field, file_type_code) for field in (fields or [])]
    result.sort(key=lambda item: item.get("order") or 0)
    return result
