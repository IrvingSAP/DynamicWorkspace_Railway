"""Comparador 1:1 FILE MATCH (match_run.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DETAIL_PREVIEW_LIMIT = 200
ROW_HARD_LIMIT = 50_000


@dataclass
class MatchEngineResult:
    verdict: str  # passed | failed | partial
    metrics: dict[str, Any] = field(default_factory=dict)
    detail: list[dict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def _norm_token(value: Any, *, trim: bool, case_fold: bool) -> str:
    text = "" if value is None else str(value)
    if trim:
        text = text.strip()
    if case_fold:
        text = text.casefold()
    return text


def _build_key(
    row: dict,
    key_pairs: list[dict],
    *,
    side: str,
    trim: bool,
    case_fold: bool,
) -> tuple[str, ...]:
    parts: list[str] = []
    for pair in key_pairs:
        field_name = (pair.get(side) or "").strip()
        parts.append(_norm_token(row.get(field_name), trim=trim, case_fold=case_fold))
    return tuple(parts)


def _key_label(key: tuple[str, ...]) -> str:
    return " | ".join(key)


def _compare_values(
    row_a: dict,
    row_b: dict,
    compare_pairs: list[dict],
    *,
    trim: bool,
    case_fold: bool,
) -> list[dict]:
    diffs: list[dict] = []
    for pair in compare_pairs:
        name_a = (pair.get("a") or "").strip()
        name_b = (pair.get("b") or "").strip()
        va = _norm_token(row_a.get(name_a), trim=trim, case_fold=case_fold)
        vb = _norm_token(row_b.get(name_b), trim=trim, case_fold=case_fold)
        if va != vb:
            diffs.append(
                {
                    "a": name_a,
                    "b": name_b,
                    "value_a": "" if row_a.get(name_a) is None else str(row_a.get(name_a)),
                    "value_b": "" if row_b.get(name_b) is None else str(row_b.get(name_b)),
                }
            )
    return diffs


def run_match(
    rows_a: list[dict],
    rows_b: list[dict],
    rules: dict,
    *,
    truncated: bool = False,
) -> MatchEngineResult:
    """Empareja filas A/B 1:1 por clave y clasifica buckets."""
    key_pairs = list(rules.get("key") or [])
    compare_pairs = list(rules.get("compare") or [])
    normalize = rules.get("normalize") or {}
    trim = bool(normalize.get("trim", True))
    case_fold_keys = bool(normalize.get("case_fold_keys", True))
    # MVP: same normalize flags for compare values (trim always; case only if keys fold)
    case_fold_compare = case_fold_keys
    on_duplicate = (rules.get("on_duplicate_key") or "bucket").strip()
    verdict_cfg = rules.get("verdict") or {}

    index_a: dict[tuple[str, ...], list[dict]] = {}
    index_b: dict[tuple[str, ...], list[dict]] = {}

    for row in rows_a:
        key = _build_key(row, key_pairs, side="a", trim=trim, case_fold=case_fold_keys)
        index_a.setdefault(key, []).append(row)
    for row in rows_b:
        key = _build_key(row, key_pairs, side="b", trim=trim, case_fold=case_fold_keys)
        index_b.setdefault(key, []).append(row)

    all_keys = set(index_a) | set(index_b)
    counts = {
        "matched": 0,
        "value_mismatch": 0,
        "only_a": 0,
        "only_b": 0,
        "duplicate_key": 0,
    }
    detail: list[dict] = []
    messages: list[str] = []

    def add_detail(item: dict) -> None:
        if len(detail) < DETAIL_PREVIEW_LIMIT:
            detail.append(item)

    for key in sorted(all_keys, key=_key_label):
        list_a = index_a.get(key) or []
        list_b = index_b.get(key) or []
        label = _key_label(key)

        if len(list_a) > 1 or len(list_b) > 1:
            counts["duplicate_key"] += 1
            add_detail(
                {
                    "bucket": "duplicate_key",
                    "key": label,
                    "count_a": len(list_a),
                    "count_b": len(list_b),
                    "diffs": [],
                }
            )
            continue

        if list_a and not list_b:
            counts["only_a"] += 1
            add_detail({"bucket": "only_a", "key": label, "diffs": []})
            continue

        if list_b and not list_a:
            counts["only_b"] += 1
            add_detail({"bucket": "only_b", "key": label, "diffs": []})
            continue

        # 1:1
        diffs = _compare_values(
            list_a[0],
            list_b[0],
            compare_pairs,
            trim=trim,
            case_fold=case_fold_compare,
        )
        if diffs:
            counts["value_mismatch"] += 1
            add_detail(
                {
                    "bucket": "value_mismatch",
                    "key": label,
                    "diffs": diffs,
                }
            )
        else:
            counts["matched"] += 1
            # matched usually omitted from preview unless empty compare and few rows
            if not compare_pairs and counts["matched"] <= 20:
                add_detail({"bucket": "matched", "key": label, "diffs": []})

    if on_duplicate == "fail" and counts["duplicate_key"]:
        messages.append("Hay claves duplicadas; la política exige fallar el job.")

    fail = False
    if verdict_cfg.get("fail_on_only_a", True) and counts["only_a"]:
        fail = True
    if verdict_cfg.get("fail_on_only_b", True) and counts["only_b"]:
        fail = True
    if verdict_cfg.get("fail_on_mismatch", True) and counts["value_mismatch"]:
        fail = True
    if verdict_cfg.get("fail_on_duplicate_key", False) and counts["duplicate_key"]:
        fail = True
    if on_duplicate == "fail" and counts["duplicate_key"]:
        fail = True

    if truncated:
        verdict = "partial"
        messages.append("Se alcanzó el tope de filas; el resultado es parcial.")
    elif fail:
        verdict = "failed"
    else:
        verdict = "passed"

    total_keys = sum(counts.values()) or 1
    match_pct = round(100.0 * counts["matched"] / total_keys, 1)

    metrics = {
        "rows_a": len(rows_a),
        "rows_b": len(rows_b),
        "keys_total": len(all_keys),
        **counts,
        "match_pct": match_pct,
        "truncated": truncated,
        "detail_preview_count": len(detail),
        "detail_capped": len(all_keys) > DETAIL_PREVIEW_LIMIT
        or (counts["matched"] > 0 and compare_pairs),
    }
    return MatchEngineResult(
        verdict=verdict,
        metrics=metrics,
        detail=detail,
        messages=messages,
    )
