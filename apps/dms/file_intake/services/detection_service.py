"""Heurísticas post-upload: tipo, encoding, line ending, delimitador."""

from __future__ import annotations

from pathlib import Path

from apps.dms.file_intake.constants import DETECTION_SAMPLE_BYTES, PREVIEW_LINE_LIMIT
from apps.dms.file_intake.services.storage_service import absolute_from_stored
from apps.dms.models import SourceFileType


def extension_of(filename: str) -> str:
    name = (filename or "").lower().strip()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1]


def allowed_extensions_for_project(project) -> list[str]:
    """Extensiones del SourceProfile del borrador, o todas MVP activas."""
    from apps.dms.source_profile.services import source_persistence_service

    try:
        source = source_persistence_service.get_source_dict(project)
        code = (source.get("file_type_code") or "").strip()
    except Exception:
        code = ""

    qs = SourceFileType.objects.filter(is_active=True, phase="mvp")
    if code:
        match = qs.filter(code=code).first()
        if match and match.extensions:
            return [str(ext).lower() for ext in match.extensions]

    extensions: list[str] = []
    for item in qs:
        for ext in item.extensions or []:
            ext_l = str(ext).lower()
            if ext_l not in extensions:
                extensions.append(ext_l)
    return extensions or [".txt", ".csv", ".xlsx", ".xls"]


def suggest_file_type(filename: str, sample_text: str | None) -> str | None:
    ext = extension_of(filename)
    if ext in {".xlsx", ".xls"}:
        return "xlsx"
    if ext == ".csv":
        return "csv"
    if ext == ".txt" and sample_text is not None:
        lines = [line for line in sample_text.splitlines() if line.strip()][:50]
        if len(lines) >= 3:
            lengths = {len(line) for line in lines}
            if len(lengths) == 1 and next(iter(lengths)) > 20:
                return "txt_fixed"
            for delim in (",", ";", "\t", "|"):
                counts = [line.count(delim) for line in lines]
                if min(counts) > 0 and max(counts) == min(counts):
                    return "txt_delimited"
        return "txt_delimited"
    if ext == ".txt":
        return "txt_fixed"
    return None


def detect_encoding(raw: bytes) -> str:
    if not raw:
        return "utf-8"
    try:
        import charset_normalizer

        result = charset_normalizer.from_bytes(raw).best()
        if result and result.encoding:
            enc = result.encoding.lower().replace("_", "-")
            if enc in {"utf-8", "utf8", "ascii"}:
                return "utf-8"
            if enc in {"iso-8859-1", "latin-1", "latin1", "windows-1252", "cp1252"}:
                return "latin-1"
            return enc
    except Exception:
        pass
    for enc in ("utf-8", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def detect_line_ending(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    # Count lone LF and CR roughly
    lf = raw.count(b"\n") - crlf
    cr = raw.count(b"\r") - crlf
    if crlf >= lf and crlf >= cr and crlf > 0:
        return "crlf"
    if lf >= cr and lf > 0:
        return "lf"
    if cr > 0:
        return "cr"
    return "lf"


def detect_delimiter(sample_text: str) -> str | None:
    lines = [line for line in sample_text.splitlines() if line.strip()][:30]
    if not lines:
        return None
    best = None
    best_score = 0
    for delim in (",", ";", "\t", "|"):
        counts = [line.count(delim) for line in lines]
        if min(counts) <= 0:
            continue
        if max(counts) != min(counts):
            continue
        score = min(counts)
        if score > best_score:
            best_score = score
            best = delim
    return best


def build_suggestions(filename: str, stored_path: str) -> dict:
    abs_path = absolute_from_stored(stored_path)
    raw = b""
    if abs_path.is_file():
        with abs_path.open("rb") as fh:
            raw = fh.read(DETECTION_SAMPLE_BYTES)

    ext = extension_of(filename)
    sample_text = None
    encoding = "utf-8"
    line_ending = "lf"
    delimiter = None

    if ext not in {".xlsx", ".xls"} and raw:
        encoding = detect_encoding(raw)
        line_ending = detect_line_ending(raw)
        try:
            sample_text = raw.decode(encoding, errors="replace")
        except Exception:
            sample_text = raw.decode("utf-8", errors="replace")
        delimiter = detect_delimiter(sample_text)

    file_type = suggest_file_type(filename, sample_text)
    return {
        "file_type_code": file_type,
        "encoding_code": encoding if encoding != "utf-8" else "utf-8",
        "line_ending_code": line_ending,
        "delimiter": delimiter,
        "extension": ext,
    }


def preview_rows(stored_path: str, *, filename: str = "", limit: int = PREVIEW_LINE_LIMIT) -> list[dict]:
    abs_path = absolute_from_stored(stored_path)
    if not abs_path.is_file():
        return []
    ext = extension_of(filename or abs_path.name)
    if ext in {".xlsx", ".xls"}:
        return [
            {
                "line": 1,
                "raw": "(archivo Excel — preview textual no disponible en MVP)",
                "parsed": None,
            }
        ]

    with abs_path.open("rb") as fh:
        raw = fh.read(DETECTION_SAMPLE_BYTES * 2)
    encoding = detect_encoding(raw)
    text = raw.decode(encoding, errors="replace")
    rows = []
    for index, line in enumerate(text.splitlines(), start=1):
        if index > limit:
            break
        rows.append({"line": index, "raw": line, "parsed": None})
    return rows


def human_size(num_bytes: int) -> str:
    value = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"
