"""Resolución de output_filename_pattern (transform_execution.md)."""

from __future__ import annotations

import re
from datetime import datetime

from apps.dms.file_intake.services.storage_service import sanitize_filename

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")


def resolve_output_filename(
    pattern: str,
    *,
    project,
    version_number: int,
    job_id: str,
    target_file_type: str,
    now: datetime | None = None,
) -> str:
    when = now or datetime.now()
    slug = getattr(project, "slug", "") or "project"
    name = sanitize_filename(getattr(project, "name", "") or slug).replace(" ", "_")
    ext_map = {
        "csv": ".csv",
        "txt_delimited": ".txt",
        "txt_fixed": ".txt",
        "xlsx": ".xlsx",
        "json": ".json",
        "xml": ".xml",
    }
    ext = ext_map.get((target_file_type or "").strip(), ".txt")

    def repl(match: re.Match) -> str:
        token = (match.group(1) or "").strip()
        if token == "project":
            return slug
        if token == "project_name":
            return name
        if token == "date":
            return when.strftime("%Y%m%d")
        if token.startswith("date:"):
            fmt = token.split(":", 1)[1] or "%Y%m%d"
            try:
                return when.strftime(fmt)
            except ValueError:
                return when.strftime("%Y%m%d")
        if token == "datetime":
            return when.strftime("%Y%m%dT%H%M%S")
        if token == "job_id":
            return str(job_id).replace("-", "")[:8]
        if token == "version":
            return str(version_number)
        if token == "ext":
            return ext.lstrip(".")
        return ""

    resolved = _TOKEN_RE.sub(repl, pattern or f"salida_{{date}}{ext}")
    resolved = sanitize_filename(resolved)
    if "." not in resolved:
        resolved = f"{resolved}{ext}"
    return resolved
