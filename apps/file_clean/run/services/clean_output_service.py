"""Serialización de salida File Clean (mismo file_type que el perfil publicado)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from apps.dms.file_intake.services import storage_service
from apps.dms.transform_execution.services import target_serializer_service
from apps.file_clean.run.services import clean_engine_service as engine
from apps.projects.models import Project


class CleanOutputError(Exception):
    pass


def source_as_target(source: dict) -> dict:
    """Adapta SourceProfile dict a la forma que espera serialize_rows."""
    config = source.get("config") or {}
    file_type = (source.get("file_type_code") or "").strip()
    layout = {
        "delimiter": config.get("delimiter")
        or ("," if file_type == "csv" else ";" if file_type == "txt_delimited" else ","),
        "quote_char": config.get("quote_char") or '"',
        "include_header": bool(config.get("has_header", True)),
        "sheet_name": config.get("sheet_name") or "Hoja1",
        "include_bom": False,
        "record_path": config.get("record_path") or "",
        "record_element": config.get("record_element") or "record",
    }
    # Preservar orden del perfil: serialize_rows ordena por (order, name).
    fields = []
    for index, field in enumerate(source.get("fields") or []):
        if not isinstance(field, dict):
            continue
        item = dict(field)
        if item.get("order") is None:
            item["order"] = index
        fields.append(item)
    return {
        "file_type_code": file_type,
        "fields": fields,
        "serialization": {
            "null_representation": "",
            "trim_before_write": False,
        },
        "layout": layout,
    }


def rows_for_serializer(rows: list[dict], fields: list[dict]) -> list[dict]:
    """Claves en minúsculas (contrato de target_serializer_service)."""
    names = [(f.get("name") or "").strip() for f in fields if (f.get("name") or "").strip()]
    out = []
    for row in rows:
        mapped = {}
        for name in names:
            if name in row:
                mapped[name.lower()] = row[name]
            elif name.lower() in row:
                mapped[name.lower()] = row[name.lower()]
            else:
                mapped[name.lower()] = ""
        out.append(mapped)
    return out


def default_output_filename(original_name: str, file_type: str) -> str:
    stem = Path(original_name or "archivo").stem or "archivo"
    ext_map = {
        "csv": ".csv",
        "txt_delimited": ".txt",
        "txt_fixed": ".txt",
        "xlsx": ".xlsx",
        "json": ".json",
        "xml": ".xml",
    }
    ext = ext_map.get((file_type or "").strip(), Path(original_name or "").suffix or ".txt")
    return f"{stem}_clean{ext}"


def encode_output_bytes(raw: bytes, rules: list[dict]) -> bytes:
    """Aplica encoding_normalize al buffer serializado (utf-8 por defecto)."""
    params = engine.encoding_params(rules)
    if not params:
        return raw
    target = (params.get("target_encoding") or "utf-8").lower()
    strip_bom = bool(params.get("strip_bom", True))
    text = raw.decode("utf-8", errors="replace")
    if strip_bom and text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    if target in {"utf-8", "utf8", ""}:
        body = text.encode("utf-8")
        if strip_bom and body.startswith(b"\xef\xbb\xbf"):
            body = body[3:]
        return body
    if target in {"latin-1", "latin1", "iso-8859-1", "windows-1252", "cp1252"}:
        return text.encode("latin-1", errors="replace")
    try:
        return text.encode(target, errors="replace")
    except LookupError:
        return text.encode("utf-8")


def serialize_clean_rows(rows: list[dict], source: dict, rules: list[dict]) -> bytes:
    target = source_as_target(source)
    prepared = rows_for_serializer(rows, target.get("fields") or [])
    try:
        raw = target_serializer_service.serialize_rows(prepared, target)
    except target_serializer_service.SerializeError as exc:
        raise CleanOutputError(str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise CleanOutputError(
            "No se pudo escribir el archivo de salida con el layout publicado."
        ) from exc
    return encode_output_bytes(raw, rules)


def write_change_log_artifacts(
    project: Project,
    job_id,
    change_log: list[dict],
) -> str:
    """Escribe change_log.json + change_log.csv. Devuelve path relativo del JSON."""
    reports_dir = storage_service.job_reports_dir(project.company_id, project.id, job_id)
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_abs = reports_dir / "change_log.json"
    json_abs.write_text(
        json.dumps(change_log, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "field", "rule", "before", "after"])
    for entry in change_log:
        writer.writerow(
            [
                entry.get("row", ""),
                entry.get("field", ""),
                entry.get("rule", ""),
                entry.get("before", ""),
                entry.get("after", ""),
            ]
        )
    csv_abs = reports_dir / "change_log.csv"
    csv_abs.write_text(buffer.getvalue(), encoding="utf-8")

    return storage_service.relative_to_media(json_abs)


def write_output_file(
    project: Project,
    job_id,
    content: bytes,
    filename: str,
) -> tuple[str, int, str]:
    """Persiste output. Retorna (stored_path relativo, size, sha256)."""
    out_dir = storage_service.job_output_dir(project.company_id, project.id, job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = storage_service.sanitize_filename(filename)
    absolute = out_dir / safe
    absolute.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    return storage_service.relative_to_media(absolute), len(content), digest


def build_preview(
    before_rows: list[dict],
    after_rows: list[dict],
    fields: list[dict],
    *,
    limit: int = 20,
) -> dict:
    names = [(f.get("name") or "").strip() for f in fields if (f.get("name") or "").strip()]
    before_slice = before_rows[:limit]
    after_slice = after_rows[:limit]
    return {
        "field_names": names,
        "limit": limit,
        "before": before_slice,
        "after": after_slice,
        "rows_shown": max(len(before_slice), len(after_slice)),
    }
