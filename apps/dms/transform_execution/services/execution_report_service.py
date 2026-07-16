"""Generación de informes de ejecución (JSON / CSV / HTML)."""

from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path

from apps.dms.transform_execution.services import execution_error_catalog_service as error_catalog


def _status_label(status: str) -> str:
    labels = {
        "completed": "Completado",
        "partial": "Parcial",
        "failed": "Fallido",
        "ok": "OK",
    }
    return labels.get(status, status)


def build_report_data(
    *,
    job_id: str,
    version_number: int,
    input_filename: str,
    input_size: int,
    output_filename: str,
    rows_read: int,
    rows_ok: int,
    errors: list[dict],
    processing_report: dict | None,
    extra_messages: list[dict] | None = None,
) -> dict:
    report_cfg = processing_report or {}
    localized_errors = error_catalog.localize_row_errors(errors)
    rejected_lines = {
        err["line"] for err in localized_errors if err.get("line") is not None
    }
    rows_rejected = len(rejected_lines)
    reject_rate = round(100.0 * rows_rejected / max(rows_read, 1), 2)

    status = "partial" if rows_rejected else "ok"
    if rows_read == 0 and localized_errors:
        status = "failed"

    report: dict = {
        "job_id": job_id,
        "project_version": version_number,
        "status": status,
        "input": {
            "original_filename": input_filename,
            "size_bytes": input_size,
        },
        "output": {"filename": output_filename},
    }

    if report_cfg.get("include_summary", True):
        report["summary"] = {
            "rows_read": rows_read,
            "rows_ok": rows_ok,
            "rows_rejected": rows_rejected,
            "reject_rate_percent": reject_rate,
        }

    messages: list[dict] = []
    for msg in error_catalog.localize_report_messages(extra_messages or []):
        if isinstance(msg, dict) and msg.get("text"):
            messages.append(
                {
                    "level": msg.get("level") or "warning",
                    "code": msg.get("code") or "",
                    "text": msg["text"],
                }
            )
    threshold = report_cfg.get("reject_alert_threshold")
    unit = report_cfg.get("reject_alert_threshold_unit") or "count"
    if threshold is not None and report_cfg.get("report_enabled", True):
        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            threshold_value = None
        if threshold_value is not None:
            exceeded = (
                reject_rate > threshold_value
                if unit == "percent"
                else rows_rejected > threshold_value
            )
            if exceeded:
                messages.append(
                    {
                        "level": "warning",
                        "text": (
                            f"Los rechazos superaron el umbral configurado "
                            f"({threshold_value:g} {unit})."
                        ),
                    }
                )
    if rows_rejected:
        messages.append(
            {
                "level": "warning",
                "text": f"{rows_rejected} registros no cumplieron con lo requerido.",
            }
        )
    if messages:
        report["messages"] = messages

    if report_cfg.get("include_row_errors", True):
        report["row_errors"] = localized_errors[:1000]

    return report


def render_html_report(report: dict) -> str:
    summary = report.get("summary") or {}
    messages = report.get("messages") or []
    row_errors = report.get("row_errors") or []
    status = report.get("status", "—")

    rows_html = ""
    for err in row_errors[:500]:
        rows_html += (
            "<tr>"
            f"<td>{escape(str(err.get('line', '')))}</td>"
            f"<td>{escape(str(err.get('field', '')))}</td>"
            f"<td><code>{escape(str(err.get('code', '')))}</code></td>"
            f"<td>{escape(str(err.get('message', '')))}</td>"
            f"<td>{escape(str(err.get('value', '')))}</td>"
            "</tr>"
        )

    messages_html = "".join(
        f'<li class="report-msg report-msg--{escape(msg.get("level", "info"))}">'
        f"{escape(msg.get('text', ''))}</li>"
        for msg in messages
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Informe de transformación</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1a1f36; }}
    h1 {{ font-size: 1.35rem; margin-bottom: 8px; }}
    .meta {{ color: #6b7194; font-size: 0.9rem; margin-bottom: 20px; }}
    .status {{ display: inline-block; padding: 4px 10px; border-radius: 999px;
               background: #e8eef4; font-weight: 600; font-size: 0.85rem; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 16px 0 24px; }}
    .metric {{ padding: 12px 14px; border: 1px solid #d4d9e0; border-radius: 8px; }}
    .metric strong {{ display: block; font-size: 1.25rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th, td {{ border: 1px solid #d4d9e0; padding: 8px 10px; text-align: left; }}
    th {{ background: #f7f9fb; }}
    .report-msg {{ margin: 4px 0; }}
    .report-msg--warning {{ color: #b45309; }}
  </style>
</head>
<body>
  <h1>Informe de transformación</h1>
  <p class="meta">Job {escape(str(report.get("job_id", "")))} · Versión v{escape(str(report.get("project_version", "")))}</p>
  <p>Estado: <span class="status">{escape(_status_label(status))}</span></p>
  <div class="summary">
    <div class="metric"><span>Filas leídas</span><strong>{escape(str(summary.get("rows_read", 0)))}</strong></div>
    <div class="metric"><span>Filas OK</span><strong>{escape(str(summary.get("rows_ok", 0)))}</strong></div>
    <div class="metric"><span>Rechazadas</span><strong>{escape(str(summary.get("rows_rejected", 0)))}</strong></div>
    <div class="metric"><span>% rechazo</span><strong>{escape(str(summary.get("reject_rate_percent", 0)))}</strong></div>
  </div>
  {"<ul>" + messages_html + "</ul>" if messages_html else ""}
  {"<h2>Detalle por fila</h2><table><thead><tr><th>Línea</th><th>Campo</th><th>Código</th><th>Mensaje</th><th>Valor</th></tr></thead><tbody>" + rows_html + "</tbody></table>" if rows_html else ""}
</body>
</html>"""


def write_execution_reports(
    reports_dir: Path,
    report: dict,
    errors: list[dict],
    processing_report: dict | None,
) -> tuple[str, str]:
    """
    Escribe informe principal y CSV de errores.

    Returns:
        (relative_report_filename, primary_format)
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    cfg = processing_report or {}
    if not cfg.get("report_enabled", True):
        return "", "disabled"

    fmt = (cfg.get("report_format") or "json").strip().lower()
    if fmt not in {"json", "csv", "html"}:
        fmt = "json"

    if fmt == "html":
        report_abs = reports_dir / "report.html"
        report_abs.write_text(render_html_report(report), encoding="utf-8")
        primary_name = "report.html"
    elif fmt == "csv":
        report_abs = reports_dir / "report.csv"
        with report_abs.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            summary = report.get("summary") or {}
            writer.writerow(["metric", "value"])
            for key, value in summary.items():
                writer.writerow([key, value])
            writer.writerow([])
            writer.writerow(["line", "field", "code", "message", "value"])
            for err in report.get("row_errors") or []:
                writer.writerow(
                    [
                        err.get("line"),
                        err.get("field"),
                        err.get("code"),
                        err.get("message"),
                        err.get("value"),
                    ]
                )
        primary_name = "report.csv"
    else:
        report_abs = reports_dir / "report.json"
        report_abs.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        primary_name = "report.json"

    errors_abs = reports_dir / "errors.csv"
    localized_for_csv = report.get("row_errors") or error_catalog.localize_row_errors(errors)
    with errors_abs.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["line", "field", "code", "message", "value"]
        )
        writer.writeheader()
        for err in localized_for_csv:
            writer.writerow(
                {
                    "line": err.get("line"),
                    "field": err.get("field"),
                    "code": err.get("code"),
                    "message": err.get("message"),
                    "value": err.get("value"),
                }
            )

    return primary_name, fmt


def localize_payload_errors(
    errors: list[dict] | None = None,
    messages: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Localiza errores/mensajes para dry-run u otras respuestas UI."""
    return (
        error_catalog.localize_row_errors(errors),
        error_catalog.localize_report_messages(messages),
    )