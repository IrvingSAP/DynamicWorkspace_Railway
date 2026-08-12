"""Motor Split/Merge — aplica reglas publicadas sobre filas parseadas."""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.file_split_merge.rules.services import split_merge_rules_catalog as catalog

MAX_PARTS = 200

MSG_SPLIT_LIMIT = (
    f"Demasiadas partes (máximo {MAX_PARTS}). "
    "Ajuste las reglas de partición o el archivo de entrada."
)
MSG_MERGE_COLUMNS = (
    "Columnas incompatibles con el perfil publicado. "
    "Revise missing_columns o el layout de los archivos."
)
MSG_NO_PARTITION = "La versión publicada no tiene una regla de partición habilitada."


class SmEngineError(Exception):
    def __init__(self, message: str, *, error_code: str = "file_sm_rule_runtime"):
        super().__init__(message)
        self.error_code = error_code


@dataclass
class PartSpec:
    key: str
    label: str
    rows: list[dict]


@dataclass
class EngineResult:
    operation: str
    parts: list[PartSpec] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    keep_header: bool = True
    include_header: bool = True


def enabled_rules(rules: list[dict]) -> list[dict]:
    rows = [r for r in rules if isinstance(r, dict) and bool(r.get("enabled", True))]
    rows.sort(key=lambda r: int(r.get("sort_order") or 0))
    return rows


def _cell(row: dict, name: str):
    if name in row:
        return row[name]
    lower = name.lower()
    for key, value in row.items():
        if str(key).lower() == lower:
            return value
    return None


def _estimate_row_bytes(row: dict, field_names: list[str]) -> int:
    total = 0
    for name in field_names:
        value = _cell(row, name)
        if value is None:
            value = ""
        total += len(str(value).encode("utf-8")) + 1
    return max(total, 1)


def _safe_part_key(index: int, label: str = "") -> str:
    return f"part_{index:03d}"


def split_rows(
    rows: list[dict],
    rules: list[dict],
    *,
    field_names: list[str],
) -> EngineResult:
    active = enabled_rules(rules)
    keep_header = True
    for rule in active:
        if rule.get("code") == "keep_header":
            params = rule.get("params") or {}
            if "value" in params:
                keep_header = bool(params.get("value"))
            break

    partition = None
    for rule in active:
        if rule.get("code") in catalog.SPLIT_PARTITION_CODES:
            partition = rule
            break
    if partition is None:
        raise SmEngineError(MSG_NO_PARTITION, error_code="file_sm_no_partition")

    code = partition.get("code")
    params = partition.get("params") or {}
    parts: list[PartSpec] = []

    if code == "max_rows":
        n = max(1, int(params.get("n") or 1))
        chunks = [rows[i : i + n] for i in range(0, len(rows), n)]
        if len(chunks) > MAX_PARTS:
            raise SmEngineError(MSG_SPLIT_LIMIT, error_code="file_sm_split_limit")
        for index, chunk in enumerate(chunks, start=1):
            key = _safe_part_key(index)
            parts.append(PartSpec(key=key, label=f"Filas {(index - 1) * n + 1}–{(index - 1) * n + len(chunk)}", rows=chunk))

    elif code == "max_bytes":
        limit = max(1, int(params.get("bytes") or 1))
        current: list[dict] = []
        current_bytes = 0
        index = 1
        for row in rows:
            row_bytes = _estimate_row_bytes(row, field_names)
            if current and current_bytes + row_bytes > limit:
                key = _safe_part_key(index)
                parts.append(PartSpec(key=key, label=f"Parte {index} (~{current_bytes} B)", rows=current))
                index += 1
                if index > MAX_PARTS:
                    raise SmEngineError(MSG_SPLIT_LIMIT, error_code="file_sm_split_limit")
                current = []
                current_bytes = 0
            current.append(row)
            current_bytes += row_bytes
        if current:
            if index > MAX_PARTS:
                raise SmEngineError(MSG_SPLIT_LIMIT, error_code="file_sm_split_limit")
            key = _safe_part_key(index)
            parts.append(PartSpec(key=key, label=f"Parte {index} (~{current_bytes} B)", rows=current))

    elif code == "split_by_column":
        field_name = (params.get("field_name") or "").strip()
        include_empty = bool(params.get("include_empty"))
        groups: dict[str, list[dict]] = {}
        order: list[str] = []
        for row in rows:
            raw = _cell(row, field_name)
            text = "" if raw is None else str(raw).strip()
            if text == "" and not include_empty:
                continue
            bucket = text if text else "(vacío)"
            if bucket not in groups:
                groups[bucket] = []
                order.append(bucket)
            groups[bucket].append(row)
        if len(order) > MAX_PARTS:
            raise SmEngineError(MSG_SPLIT_LIMIT, error_code="file_sm_split_limit")
        for index, bucket in enumerate(order, start=1):
            key = _safe_part_key(index)
            parts.append(
                PartSpec(
                    key=key,
                    label=f"{field_name}={bucket}",
                    rows=groups[bucket],
                )
            )
    else:
        raise SmEngineError(MSG_NO_PARTITION, error_code="file_sm_no_partition")

    if not parts:
        raise SmEngineError(
            "La partición no produjo ninguna parte. Revise include_empty o el archivo.",
            error_code="file_sm_parse_empty",
        )

    metrics = {
        "rows_read": len(rows),
        "parts_count": len(parts),
        "partition_code": code,
        "rows_written": sum(len(p.rows) for p in parts),
    }
    return EngineResult(
        operation=catalog.OPERATION_SPLIT,
        parts=parts,
        metrics=metrics,
        keep_header=keep_header,
    )


def _row_has_field(row: dict, name: str) -> bool:
    if name in row:
        return True
    lower = name.lower()
    return any(str(k).lower() == lower for k in row.keys())


def merge_row_sets(
    row_sets: list[tuple[str, list[dict]]],
    rules: list[dict],
    *,
    field_names: list[str],
) -> EngineResult:
    active = enabled_rules(rules)
    missing_mode = "error"
    include_header = True
    dedupe = None
    for rule in active:
        code = rule.get("code")
        params = rule.get("params") or {}
        if code == "missing_columns":
            missing_mode = (params.get("mode") or "error").strip()
        elif code == "include_header":
            if "value" in params:
                include_header = bool(params.get("value"))
        elif code == "dedupe_rows":
            dedupe = params

    merged: list[dict] = []
    for filename, rows in row_sets:
        for row in rows:
            aligned: dict = {}
            for name in field_names:
                if not _row_has_field(row, name):
                    if missing_mode == "error":
                        raise SmEngineError(
                            f"{MSG_MERGE_COLUMNS} Archivo «{filename}», falta «{name}».",
                            error_code="file_sm_merge_columns",
                        )
                    aligned[name] = ""
                    continue
                value = _cell(row, name)
                aligned[name] = "" if value is None else value
            merged.append(aligned)

    dedupe_removed = 0
    if dedupe:
        keys = [str(k).strip() for k in (dedupe.get("keys") or []) if str(k).strip()]
        keep = (dedupe.get("keep") or "first").strip()
        if keys:
            seen: dict[tuple, int] = {}
            result_rows: list[dict] = []
            for row in merged:
                key = tuple(str(_cell(row, k) or "") for k in keys)
                if key in seen:
                    dedupe_removed += 1
                    if keep == "last":
                        result_rows[seen[key]] = row
                    continue
                seen[key] = len(result_rows)
                result_rows.append(row)
            merged = result_rows

    metrics = {
        "rows_read": sum(len(rows) for _, rows in row_sets),
        "files_count": len(row_sets),
        "rows_written": len(merged),
        "dedupe_removed": dedupe_removed,
        "parts_count": 1,
    }
    return EngineResult(
        operation=catalog.OPERATION_MERGE,
        rows=merged,
        metrics=metrics,
        include_header=include_header,
    )
