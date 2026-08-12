"""Serialización y artifacts File Split/Merge."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from apps.dms.file_intake.services import storage_service
from apps.dms.transform_execution.services import target_serializer_service
from apps.file_split_merge.run.services.sm_engine_service import EngineResult, PartSpec
from apps.projects.models import Project


class SmOutputError(Exception):
    pass


def source_as_target(source: dict, *, include_header: bool | None = None) -> dict:
    config = source.get("config") or {}
    file_type = (source.get("file_type_code") or "").strip()
    if include_header is None:
        header = bool(config.get("has_header", True))
    else:
        header = bool(include_header)
    layout = {
        "delimiter": config.get("delimiter")
        or ("," if file_type == "csv" else ";" if file_type == "txt_delimited" else ","),
        "quote_char": config.get("quote_char") or '"',
        "include_header": header,
        "sheet_name": config.get("sheet_name") or "Hoja1",
        "include_bom": False,
        "record_path": config.get("record_path") or "",
        "record_element": config.get("record_element") or "record",
    }
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


def extension_for_type(file_type: str, original_name: str = "") -> str:
    ext_map = {
        "csv": ".csv",
        "txt_delimited": ".txt",
        "txt_fixed": ".txt",
        "xlsx": ".xlsx",
        "json": ".json",
        "xml": ".xml",
    }
    return ext_map.get((file_type or "").strip(), Path(original_name or "").suffix or ".txt")


def serialize_rows(rows: list[dict], source: dict, *, include_header: bool | None = None) -> bytes:
    target = source_as_target(source, include_header=include_header)
    prepared = rows_for_serializer(rows, target.get("fields") or [])
    try:
        return target_serializer_service.serialize_rows(prepared, target)
    except target_serializer_service.SerializeError as exc:
        raise SmOutputError(str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise SmOutputError(
            "No se pudo escribir el archivo de salida con el layout publicado."
        ) from exc


def write_bytes_artifact(
    project: Project,
    job_id,
    content: bytes,
    filename: str,
) -> tuple[str, int, str]:
    out_dir = storage_service.job_output_dir(project.company_id, project.id, job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = storage_service.sanitize_filename(filename)
    absolute = out_dir / safe
    absolute.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    return storage_service.relative_to_media(absolute), len(content), digest


def write_manifest(
    project: Project,
    job_id,
    manifest: dict,
) -> tuple[str, int, str]:
    reports_dir = storage_service.job_reports_dir(project.company_id, project.id, job_id)
    reports_dir.mkdir(parents=True, exist_ok=True)
    absolute = reports_dir / "manifest.json"
    body = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    absolute.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    return storage_service.relative_to_media(absolute), len(body), digest


def write_split_artifacts(
    project: Project,
    job_id,
    result: EngineResult,
    source: dict,
    *,
    original_name: str,
) -> tuple[list[dict], str]:
    """Persiste partes + manifiesto + ZIP. Retorna (outputs[], manifest_path)."""
    file_type = source.get("file_type_code") or ""
    ext = extension_for_type(file_type, original_name)
    stem = Path(original_name or "archivo").stem or "archivo"
    outputs: list[dict] = []
    manifest_parts = []
    part_files: list[tuple[str, bytes]] = []

    for part in result.parts:
        content = serialize_rows(
            part.rows, source, include_header=result.keep_header
        )
        filename = f"{stem}_{part.key}{ext}"
        path, size, digest = write_bytes_artifact(project, job_id, content, filename)
        outputs.append(
            {
                "kind": part.key,
                "filename": filename,
                "stored_path": path,
                "size_bytes": size,
                "content_hash": digest,
                "part_key": part.key,
                "rows": len(part.rows),
                "label": part.label,
            }
        )
        part_files.append((filename, content))
        manifest_parts.append(
            {
                "part_key": part.key,
                "filename": filename,
                "rows": len(part.rows),
                "label": part.label,
                "size_bytes": size,
                "content_hash": digest,
            }
        )

    manifest = {
        "operation": "split",
        "parts_count": len(manifest_parts),
        "rows_read": (result.metrics or {}).get("rows_read"),
        "partition_code": (result.metrics or {}).get("partition_code"),
        "parts": manifest_parts,
    }
    manifest_path, m_size, m_hash = write_manifest(project, job_id, manifest)
    outputs.append(
        {
            "kind": "manifest",
            "filename": "manifest.json",
            "stored_path": manifest_path,
            "size_bytes": m_size,
            "content_hash": m_hash,
        }
    )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in part_files:
            zf.writestr(filename, content)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    zip_name = f"{stem}_parts.zip"
    zip_path, zip_size, zip_hash = write_bytes_artifact(
        project, job_id, zip_buf.getvalue(), zip_name
    )
    outputs.append(
        {
            "kind": "zip",
            "filename": zip_name,
            "stored_path": zip_path,
            "size_bytes": zip_size,
            "content_hash": zip_hash,
        }
    )
    return outputs, manifest_path


def write_merge_artifact(
    project: Project,
    job_id,
    result: EngineResult,
    source: dict,
    *,
    original_name: str,
) -> list[dict]:
    file_type = source.get("file_type_code") or ""
    ext = extension_for_type(file_type, original_name)
    stem = Path(original_name or "merged").stem or "merged"
    filename = f"{stem}_merged{ext}"
    content = serialize_rows(
        result.rows, source, include_header=result.include_header
    )
    path, size, digest = write_bytes_artifact(project, job_id, content, filename)
    return [
        {
            "kind": "merged",
            "filename": filename,
            "stored_path": path,
            "size_bytes": size,
            "content_hash": digest,
            "rows": len(result.rows),
        }
    ]


def build_split_preview(result: EngineResult, *, limit: int = 20) -> dict:
    parts_preview = []
    for part in result.parts[:50]:
        sample = part.rows[: min(3, limit)]
        parts_preview.append(
            {
                "part_key": part.key,
                "label": part.label,
                "rows": len(part.rows),
                "sample": sample,
            }
        )
    return {
        "kind": "split",
        "parts_count": len(result.parts),
        "parts": parts_preview,
        "limit": limit,
    }


def build_merge_preview(
    result: EngineResult,
    fields: list[dict],
    *,
    limit: int = 20,
) -> dict:
    names = [(f.get("name") or "").strip() for f in fields if (f.get("name") or "").strip()]
    sample = result.rows[:limit]
    return {
        "kind": "merge",
        "field_names": names,
        "rows_shown": len(sample),
        "rows": sample,
        "limit": limit,
    }
