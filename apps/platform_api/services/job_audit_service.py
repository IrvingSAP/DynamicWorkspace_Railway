"""Metadatos de disparo API en jobs y pipeline runs (M7)."""

from __future__ import annotations

import uuid
from datetime import datetime

from django.utils import timezone


def client_ip_from_meta(meta: dict) -> str:
    forwarded = str(meta.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    raw = forwarded or str(meta.get("REMOTE_ADDR") or "")
    return raw[:45]


def user_agent_from_meta(meta: dict) -> str:
    return str(meta.get("HTTP_USER_AGENT") or "")[:300]


def ensure_correlation_id(value: str | None) -> str:
    text = str(value or "").strip()
    return text[:64] if text else uuid.uuid4().hex


def duration_ms(started_at, finished_at) -> int | None:
    if started_at is None or finished_at is None:
        return None
    delta = finished_at - started_at
    return int(delta.total_seconds() * 1000)


def iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _suggestions_from_job(job) -> dict:
    data = dict(
        getattr(job, "input_suggestions", None)
        or getattr(job, "input_suggestions", None)
        or {}
    )
    if data.get("trigger_source"):
        return data
    metrics = getattr(job, "metrics", None) or {}
    api = metrics.get("api") if isinstance(metrics, dict) else None
    if isinstance(api, dict):
        return {**api, **data}
    snapshot = (
        getattr(job, "suggestions_snapshot", None)
        or getattr(job, "suggestions_snapshot", None)
        or {}
    )
    snap_api = snapshot.get("api") if isinstance(snapshot, dict) else None
    if isinstance(snap_api, dict):
        return {**snap_api, **data}
    return data


def job_audit_payload(job, *, extra: dict | None = None) -> dict:
    data = _suggestions_from_job(job)
    if extra:
        data.update(extra)
    started = getattr(job, "started_at", None)
    finished = getattr(job, "finished_at", None)
    hash_a = getattr(job, "file_a_hash", "") or getattr(job, "file_a_hash", "") or ""
    hash_b = getattr(job, "file_b_hash", "") or getattr(job, "file_b_hash", "") or ""
    match_hash = f"{hash_a}:{hash_b}" if (hash_a or hash_b) else ""
    name_a = getattr(job, "file_a_name", "") or getattr(job, "file_a_name", "") or ""
    name_b = getattr(job, "file_b_name", "") or getattr(job, "file_b_name", "") or ""
    match_name = ", ".join(part for part in (name_a, name_b) if part)
    size_a = getattr(job, "file_a_size_bytes", 0) or getattr(job, "file_a_size_bytes", 0) or 0
    size_b = getattr(job, "file_b_size_bytes", 0) or getattr(job, "file_b_size_bytes", 0) or 0
    return {
        "trigger_source": data.get("trigger_source") or "ui",
        "triggered_by_api_client_id": data.get("triggered_by_api_client_id")
        or data.get("api_client_id"),
        "api_client_id": data.get("api_client_id"),
        "idempotency_key": data.get("idempotency_key"),
        "correlation_id": data.get("correlation_id"),
        "retry_of_job_id": data.get("retry_of_job_id"),
        "client_ip": data.get("client_ip") or "",
        "user_agent": data.get("user_agent") or "",
        "dry_run": bool(data.get("dry_run")),
        "job_id": str(job.id),
        "created_at": iso(getattr(job, "created_at", None)),
        "input_hash": getattr(job, "input_content_hash", "")
        or getattr(job, "input_content_hash", "")
        or data.get("input_hash")
        or match_hash,
        "triggered_at": data.get("triggered_at"),
        "started_at": iso(started),
        "finished_at": iso(finished),
        "duration_ms": duration_ms(started, finished)
        or (getattr(job, "metrics", None) or {}).get("duration_ms"),
        "input_filename": getattr(job, "input_original_filename", "")
        or getattr(job, "input_original_filename", "")
        or match_name
        or "",
        "input_size_bytes": getattr(job, "input_size_bytes", 0)
        or getattr(job, "input_size_bytes", 0)
        or (size_a + size_b)
        or 0,
    }


def pipeline_audit_payload(run) -> dict:
    started = getattr(run, "started_at", None)
    finished = getattr(run, "finished_at", None)
    created = getattr(run, "created_at", None)
    duration = getattr(run, "duration_ms", None)
    steps = []
    step_qs = run.steps.all() if hasattr(run, "steps") else []
    for step in step_qs:
        app_job_id = getattr(step, "app_job_id", None) or None
        steps.append(
            {
                "order": step.order,
                "kind": step.kind,
                "status": step.status,
                "app_job_id": app_job_id,
                "project_slug": getattr(step, "project_slug", "") or "",
            }
        )
    return {
        "trigger_source": getattr(run, "trigger_source", "") or "ui",
        "triggered_by_api_client_id": getattr(run, "api_client_id", "") or None,
        "api_client_label": getattr(run, "api_client_label", "") or "",
        "idempotency_key": getattr(run, "idempotency_key", "") or None,
        "correlation_id": getattr(run, "correlation_id", "") or None,
        "client_ip": getattr(run, "client_ip", "") or "",
        "user_agent": getattr(run, "user_agent", "") or "",
        "dry_run": bool(getattr(run, "dry_run", False)),
        "job_id": str(run.id),
        "pipeline_run_id": str(run.id),
        "input_hash": getattr(run, "input_sha256", "") or "",
        "triggered_at": iso(created),
        "created_at": iso(created),
        "started_at": iso(started),
        "finished_at": iso(finished),
        "duration_ms": duration if duration is not None else duration_ms(started, finished),
        "input_filename": getattr(run, "input_filename", "") or "",
        "steps": steps,
    }


def stamp_job_suggestions(job, client, parsed: dict) -> dict:
    suggestions = _suggestions_from_job(job)
    suggestions["trigger_source"] = "api"
    suggestions["api_client_id"] = str(client.pk)
    suggestions["triggered_by_api_client_id"] = str(client.pk)
    suggestions["dry_run"] = bool(parsed.get("dry_run"))
    suggestions["correlation_id"] = ensure_correlation_id(parsed.get("correlation_id"))
    suggestions["idempotency_key"] = parsed.get("idempotency_key") or ""
    suggestions["client_ip"] = parsed.get("client_ip") or ""
    suggestions["user_agent"] = parsed.get("user_agent") or ""
    suggestions["triggered_at"] = timezone.now().isoformat()
    if parsed.get("retry_of_job_id"):
        suggestions["retry_of_job_id"] = parsed["retry_of_job_id"]
    hash_value = getattr(job, "input_content_hash", "") or parsed.get("content_hash") or ""
    if hash_value:
        suggestions["input_hash"] = hash_value
    if hasattr(job, "input_suggestions"):
        job.input_suggestions = suggestions
        fields = ["input_suggestions"]
        if hasattr(job, "updated_at"):
            fields.append("updated_at")
        job.save(update_fields=fields)
    elif hasattr(job, "suggestions_snapshot"):
        snapshot = dict(job.suggestions_snapshot or {})
        snapshot["api"] = suggestions
        job.suggestions_snapshot = snapshot
        fields = ["suggestions_snapshot"]
        if hasattr(job, "updated_at"):
            fields.append("updated_at")
        job.save(update_fields=fields)
    else:
        metrics = dict(job.metrics or {})
        metrics["api"] = suggestions
        job.metrics = metrics
        job.save(update_fields=["metrics"])
    parsed["correlation_id"] = suggestions["correlation_id"]
    return suggestions
