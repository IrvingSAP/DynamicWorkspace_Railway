"""Motor de validación FILE GATE — Módulo 3 (validation_run.md).

Toma el contrato publicado (source dict) + la política (gate_policy) y produce
el veredicto del gate a partir de los parsers/validadores DMS reutilizados.

No transforma ni escribe salida de negocio: solo lee y clasifica.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from apps.dms.transform_execution.services import (
    execution_error_catalog_service as error_catalog,
)
from apps.dms.transform_execution.services import source_parser_service
from apps.file_gate.policy.services import gate_policy_service

# Estados del gate (validation_run.md).
STATUS_PASSED = "passed"
STATUS_PASSED_WITH_WARNINGS = "passed_with_warnings"
STATUS_FAILED = "failed"
STATUS_PARTIAL = "partial"
STATUS_ERROR = "error"

# Motivos de decisión.
REASON_CLEAN = "clean"
REASON_WITHIN_THRESHOLD = "within_threshold"
REASON_FATAL = "fatal_error"
REASON_MAX_ERRORS = "max_errors_reached"
REASON_THRESHOLD = "reject_threshold_exceeded"

# Tope de incidencias que se guardan para vista previa en pantalla.
ISSUES_PREVIEW_LIMIT = 200


@dataclass
class GateResult:
    status: str
    decision_reason: str
    decision_message: str
    metrics: dict = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    is_success: bool = False

    @property
    def issues_preview(self) -> list[dict]:
        return self.issues[:ISSUES_PREVIEW_LIMIT]


def _decision_message(reason: str, *, threshold_label: str, max_errors: int) -> str:
    if reason == REASON_FATAL:
        return "El archivo no pudo procesarse contra el contrato (error fatal)."
    if reason == REASON_MAX_ERRORS:
        return (
            f"Se alcanzó el máximo de {max_errors} errores antes del fin del archivo; "
            "el recorrido quedó incompleto."
        )
    if reason == REASON_THRESHOLD:
        return f"El nivel de rechazo superó el máximo permitido ({threshold_label})."
    if reason == REASON_WITHIN_THRESHOLD:
        return "El archivo pasó el gate dentro del umbral permitido."
    return "El archivo cumple el contrato sin incidencias."


def build_fatal_result(message: str, *, metrics: dict | None = None) -> GateResult:
    """Resultado para un fallo fatal de contrato (p. ej. archivo no parseable)."""
    return GateResult(
        status=STATUS_FAILED,
        decision_reason=REASON_FATAL,
        decision_message=message or _decision_message(REASON_FATAL, threshold_label="—", max_errors=0),
        metrics=metrics or _empty_metrics(),
        is_success=False,
    )


def _empty_metrics() -> dict:
    return {
        "rows_read": 0,
        "rows_valid": 0,
        "rows_rejected": 0,
        "reject_rate_percent": 0.0,
        "duration_ms": 0,
        "issues_error": 0,
        "issues_warning": 0,
        "issues_info": 0,
    }


def _measured_value(policy: dict, *, rows_rejected: int, reject_rate_percent: float) -> float:
    threshold = policy.get("reject_threshold") or {}
    mode = (threshold.get("mode") or "").strip()
    if mode == gate_policy_service.THRESHOLD_MODE_COUNT:
        return float(rows_rejected)
    return float(reject_rate_percent)


def run_validation(path, source: dict, policy: dict) -> GateResult:
    """Ejecuta el pipeline de validación y devuelve el veredicto del gate.

    Lanza source_parser_service.ParseError ante fallos fatales de contrato; el
    servicio de orquestación decide cómo traducirlos.
    """
    started = time.monotonic()
    parse_result = source_parser_service.parse_source_file(path, source)
    duration_ms = int((time.monotonic() - started) * 1000)

    # Errores de campo / reglas de contenido (severidad error).
    raw_errors = list(parse_result.errors or [])
    localized_errors = error_catalog.localize_row_errors(raw_errors)
    for issue in localized_errors:
        issue["severity"] = "error"

    # Mensajes de captura (warning / info) — V8: no cuentan para umbral ni corte.
    localized_messages = error_catalog.localize_report_messages(
        list(getattr(parse_result, "messages", None) or [])
    )
    warnings: list[dict] = []
    infos: list[dict] = []
    for msg in localized_messages:
        level = (msg.get("level") or "info").strip().lower()
        entry = {
            "line": msg.get("line") or msg.get("expected_line") or "",
            "field": "",
            "code": msg.get("code") or "",
            "severity": "warning" if level == "warning" else "info",
            "message": msg.get("text") or msg.get("message") or "",
        }
        if entry["severity"] == "warning":
            warnings.append(entry)
        else:
            infos.append(entry)

    rows_read = int(parse_result.rows_read or 0)
    rows_valid = len(parse_result.rows or [])
    # V7: una fila con varios errores cuenta una sola vez.
    rejected_lines = {issue.get("line") for issue in localized_errors if issue.get("line") not in (None, "")}
    rows_rejected = len(rejected_lines)
    if rows_read == 0:
        rows_read = rows_valid + rows_rejected
    reject_rate_percent = round((rows_rejected / rows_read) * 100, 4) if rows_read else 0.0

    metrics = {
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "rows_rejected": rows_rejected,
        "reject_rate_percent": reject_rate_percent,
        "duration_ms": duration_ms,
        "issues_error": len(localized_errors),
        "issues_warning": len(warnings),
        "issues_info": len(infos),
    }

    # --- Aplicar política (delegación de semántica a gate_policy.md) ---
    max_errors = int(policy.get("max_errors") or 0)
    cut_reached = max_errors > 0 and len(localized_errors) > max_errors

    threshold = policy.get("reject_threshold") or {}
    threshold_value = float(threshold.get("value") or 0)
    measured = _measured_value(
        policy, rows_rejected=rows_rejected, reject_rate_percent=reject_rate_percent
    )
    threshold_exceeded = measured > threshold_value
    threshold_label = gate_policy_service.threshold_summary(policy)

    # Incidencias almacenadas: errores (tope max_errors) + warnings + info.
    stored_errors = localized_errors[:max_errors] if cut_reached else localized_errors
    issues = stored_errors + warnings + infos

    # --- Prioridad de decisión (validation_run.md §Semántica) ---
    # fatal > partial (corte) > failed (umbral) > passed_with_warnings > passed
    if cut_reached:
        status = STATUS_PARTIAL
        reason = REASON_MAX_ERRORS
        is_success = False
    elif threshold_exceeded:
        status = STATUS_FAILED
        reason = REASON_THRESHOLD
        is_success = False
    elif len(localized_errors) == 0 and len(warnings) == 0:
        status = STATUS_PASSED
        reason = REASON_CLEAN
        is_success = True
    else:
        status = STATUS_PASSED_WITH_WARNINGS
        reason = REASON_WITHIN_THRESHOLD
        is_success = True

    return GateResult(
        status=status,
        decision_reason=reason,
        decision_message=_decision_message(
            reason, threshold_label=threshold_label, max_errors=max_errors
        ),
        metrics=metrics,
        issues=issues,
        warnings=warnings,
        is_success=is_success,
    )
