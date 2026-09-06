"""Tablero de corridas File Pipeline (módulo D)."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.file_pipeline.models import PipelineDefinition, PipelineRun
from apps.file_pipeline.services.pipeline_history_service import actor_label, duration_label
from apps.file_pipeline.services.pipeline_project_service import visible_qs

WINDOW_CHOICES = (7, 30)
FAIL_LIMIT = 12
RECENT_LIMIT = 8
TRIGGER_ALL = "all"


def parse_window(params) -> int:
    try:
        days = int(params.get("days") or 7)
    except (TypeError, ValueError):
        days = 7
    return days if days in WINDOW_CHOICES else 7


def parse_trigger(params) -> str:
    raw = (params.get("trigger") or TRIGGER_ALL).strip()
    allowed = {code for code, _label in PipelineRun.TRIGGER_CHOICES}
    if raw in {"", TRIGGER_ALL}:
        return TRIGGER_ALL
    if raw in allowed:
        return raw
    return TRIGGER_ALL


def dashboard_context(user, params) -> dict:
    days = parse_window(params)
    trigger = parse_trigger(params)
    since = timezone.now() - timedelta(days=days)
    pipeline_ids = list(visible_qs(user).values_list("id", flat=True))

    pipelines = list(
        PipelineDefinition.objects.filter(id__in=pipeline_ids)
        .select_related("current_version")
        .order_by("slug")
    )

    window_runs = PipelineRun.objects.filter(
        pipeline_id__in=pipeline_ids,
        created_at__gte=since,
    )
    ops = window_runs.filter(dry_run=False)
    if trigger != TRIGGER_ALL:
        ops = ops.filter(trigger_source=trigger)
    dry_in_window = window_runs.filter(dry_run=True).count()

    ops_by: dict = defaultdict(int)
    fails_by: dict = defaultdict(int)
    for row in ops.values("pipeline_id", "status"):
        ops_by[row["pipeline_id"]] += 1
        if row["status"] == PipelineRun.STATUS_FAILED:
            fails_by[row["pipeline_id"]] += 1

    total = ops.count()
    completed = ops.filter(status=PipelineRun.STATUS_COMPLETED).count()
    failed = ops.filter(status=PipelineRun.STATUS_FAILED).count()
    running = ops.filter(
        status__in={PipelineRun.STATUS_RUNNING, PipelineRun.STATUS_QUEUED}
    ).count()
    fail_rate = round((failed / total) * 100) if total else 0

    by_trigger = {
        row["trigger_source"]: row["n"]
        for row in ops.values("trigger_source").annotate(n=Count("id"))
    }
    channels = []
    for code, label in PipelineRun.TRIGGER_CHOICES:
        n = by_trigger.get(code, 0)
        pct = round((n / total) * 100) if total else 0
        channels.append({"code": code, "label": label, "n": n, "pct": pct})

    fail_qs = (
        ops.filter(status=PipelineRun.STATUS_FAILED)
        .select_related("pipeline", "version", "triggered_by")
        .order_by("-created_at")[:FAIL_LIMIT]
    )
    failures = [_run_row(run) for run in fail_qs]

    recent_qs = (
        ops.select_related("pipeline", "version", "triggered_by")
        .order_by("-created_at")[:RECENT_LIMIT]
    )
    recent = [_run_row(run) for run in recent_qs]

    last_by_id = _latest_by_pipeline(pipeline_ids)
    pipeline_rows = []
    for pipeline in pipelines:
        last = last_by_id.get(pipeline.id)
        pipeline_rows.append(
            {
                "pipeline": pipeline,
                "ops_in_window": ops_by[pipeline.id],
                "fails_in_window": fails_by[pipeline.id],
                "last": last,
                "version_label": (
                    f"v{pipeline.current_version.version_number}"
                    if pipeline.current_version_id
                    else "Sin publicar"
                ),
                "status_label": pipeline.get_status_display(),
            }
        )
    pipeline_rows.sort(
        key=lambda row: (-row["fails_in_window"], -row["ops_in_window"], row["pipeline"].slug)
    )

    return {
        "days": days,
        "trigger": trigger,
        "trigger_options": [
            {"value": TRIGGER_ALL, "label": "Todos"},
            *[
                {"value": code, "label": label}
                for code, label in PipelineRun.TRIGGER_CHOICES
            ],
        ],
        "since": since,
        "pipeline_count": len(pipelines),
        "active_count": sum(
            1 for p in pipelines if p.status == PipelineDefinition.STATUS_ACTIVE
        ),
        "total": total,
        "completed": completed,
        "failed": failed,
        "running": running,
        "fail_rate": fail_rate,
        "dry_in_window": dry_in_window,
        "channels": channels,
        "failures": failures,
        "recent": recent,
        "pipeline_rows": pipeline_rows,
        "has_pipelines": bool(pipelines),
        "has_ops": total > 0,
        "has_window_activity": window_runs.exists(),
    }


def _run_row(run: PipelineRun) -> dict:
    sid = (run.schedule_id or "").strip()
    return {
        "run": run,
        "actor": actor_label(run),
        "duration": duration_label(run),
        "version_label": f"v{run.version.version_number}",
        "schedule_short": sid[:8] if sid else "",
    }


def _latest_by_pipeline(pipeline_ids: list) -> dict:
    if not pipeline_ids:
        return {}
    found: dict = {}
    qs = (
        PipelineRun.objects.filter(pipeline_id__in=pipeline_ids, dry_run=False)
        .select_related("pipeline", "version")
        .order_by("-created_at")
    )
    for run in qs:
        if run.pipeline_id in found:
            continue
        found[run.pipeline_id] = run
        if len(found) == len(pipeline_ids):
            break
    return found
