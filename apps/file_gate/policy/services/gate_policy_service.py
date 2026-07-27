"""Política de validación FILE GATE (gate_policy.md).

Persistencia: DmsSourceProfile.config["gate_policy"] — sin migración.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)

POLICY_VERSION = "1.0"
ON_ERROR_COLLECT_ALL = "collect_all"
THRESHOLD_MODE_PERCENT = "percent"
THRESHOLD_MODE_COUNT = "count"

MAX_ERRORS_MIN = 1
MAX_ERRORS_MAX = 10_000
THRESHOLD_COUNT_MAX = 10_000_000


def default_gate_policy() -> dict:
    return {
        "policy_version": POLICY_VERSION,
        "on_error": ON_ERROR_COLLECT_ALL,
        "abort_on_first_fatal": True,
        "max_errors": 500,
        "reject_threshold": {
            "mode": THRESHOLD_MODE_PERCENT,
            "value": 1.0,
        },
    }


def _as_float(value, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _import_threshold_from_report(source: dict) -> dict | None:
    """Una sola migración suave desde processing_report.reject_alert_threshold."""
    report = source.get("processing_report") or {}
    raw = report.get("reject_alert_threshold")
    if raw is None or raw == "":
        return None
    value = _as_float(raw)
    if value is None:
        return None
    unit = (report.get("reject_alert_threshold_unit") or "count").strip().lower()
    if unit in ("percent", "pct", "%"):
        mode = THRESHOLD_MODE_PERCENT
    else:
        mode = THRESHOLD_MODE_COUNT
    return {"mode": mode, "value": value}


def normalize_gate_policy(raw: dict | None, *, source: dict | None = None) -> dict:
    policy = default_gate_policy()
    incoming = raw if isinstance(raw, dict) else {}

    if not incoming and source:
        imported = _import_threshold_from_report(source)
        if imported:
            policy["reject_threshold"] = imported

    if incoming.get("policy_version"):
        policy["policy_version"] = str(incoming["policy_version"]).strip() or POLICY_VERSION

    on_error = (incoming.get("on_error") or policy["on_error"]).strip()
    policy["on_error"] = on_error

    abort = incoming.get("abort_on_first_fatal", policy["abort_on_first_fatal"])
    policy["abort_on_first_fatal"] = bool(abort) if abort is not None else True

    max_errors = _as_int(incoming.get("max_errors"), policy["max_errors"])
    if max_errors is not None:
        policy["max_errors"] = max_errors

    threshold_in = incoming.get("reject_threshold")
    if isinstance(threshold_in, dict):
        mode = (threshold_in.get("mode") or policy["reject_threshold"]["mode"]).strip()
        value = _as_float(threshold_in.get("value"), policy["reject_threshold"]["value"])
        policy["reject_threshold"] = {
            "mode": mode,
            "value": value if value is not None else policy["reject_threshold"]["value"],
        }
    elif "reject_threshold_mode" in incoming or "reject_threshold_value" in incoming:
        mode = (
            incoming.get("reject_threshold_mode")
            or policy["reject_threshold"]["mode"]
        )
        value = _as_float(
            incoming.get("reject_threshold_value"),
            policy["reject_threshold"]["value"],
        )
        policy["reject_threshold"] = {
            "mode": str(mode).strip(),
            "value": value if value is not None else policy["reject_threshold"]["value"],
        }

    return policy


def validate_gate_policy(policy: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    on_error = (policy.get("on_error") or "").strip()
    if on_error != ON_ERROR_COLLECT_ALL:
        errors.setdefault("on_error", []).append(
            "En el MVP solo se admite la estrategia Recolectar incidencias (collect_all)."
        )

    if policy.get("abort_on_first_fatal") is not True:
        errors.setdefault("abort_on_first_fatal", []).append(
            "El aborto ante error fatal debe permanecer activo."
        )

    max_errors = policy.get("max_errors")
    if not isinstance(max_errors, int) or max_errors < MAX_ERRORS_MIN or max_errors > MAX_ERRORS_MAX:
        errors.setdefault("max_errors", []).append(
            f"Indique un máximo de errores entre {MAX_ERRORS_MIN} y {MAX_ERRORS_MAX}."
        )
    elif max_errors <= 4:
        warnings.setdefault("max_errors", []).append(
            "Un tope muy bajo aumenta la probabilidad de resultado partial."
        )

    threshold = policy.get("reject_threshold") or {}
    mode = (threshold.get("mode") or "").strip()
    if mode not in (THRESHOLD_MODE_COUNT, THRESHOLD_MODE_PERCENT):
        errors.setdefault("reject_threshold_mode", []).append(
            "Seleccione umbral por cantidad o por porcentaje."
        )

    value = threshold.get("value")
    if mode == THRESHOLD_MODE_COUNT:
        as_int = _as_int(value)
        if as_int is None or as_int < 0 or as_int > THRESHOLD_COUNT_MAX:
            errors.setdefault("reject_threshold_value", []).append(
                f"El umbral por cantidad debe ser un entero entre 0 y {THRESHOLD_COUNT_MAX}."
            )
        else:
            policy["reject_threshold"]["value"] = as_int
    elif mode == THRESHOLD_MODE_PERCENT:
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            dec = None
        if dec is None or dec < 0 or dec > 100:
            errors.setdefault("reject_threshold_value", []).append(
                "El umbral porcentual debe estar entre 0 y 100."
            )
        else:
            quantized = dec.quantize(Decimal("0.0001"))
            policy["reject_threshold"]["value"] = float(quantized)
            if float(quantized) >= 100:
                warnings.setdefault("reject_threshold_value", []).append(
                    "Con 100% solo un error fatal o un corte haría fallar el gate."
                )

    return errors, warnings


def get_policy_dict(project: Project, *, persist_defaults: bool = False) -> dict:
    source = source_persistence_service.get_source_dict(project)
    config = dict(source.get("config") or {})
    raw = config.get("gate_policy")
    had_policy = isinstance(raw, dict) and bool(raw)
    policy = normalize_gate_policy(raw if had_policy else None, source=source)

    if persist_defaults and not had_policy:
        _write_policy(project, policy)

    return policy


def _write_policy(project: Project, policy: dict) -> None:
    version = source_persistence_service.get_or_create_draft_version(project)
    profile = version.source_profile
    current = source_persistence_service.profile_to_dict(profile)
    config = dict(current.get("config") or {})
    config["gate_policy"] = copy.deepcopy(policy)
    current["config"] = config
    source_persistence_service.apply_dict_to_profile(profile, current)
    profile.save()
    version.save(update_fields=["updated_at"])
    project.save(update_fields=["updated_at"])


def save_gate_policy(user, project: Project, partial: dict) -> OperationResult:
    if project.project_kind != Project.KIND_FILE_GATE:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE GATE.",
        )
    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar las políticas de este proyecto.",
        )

    current = get_policy_dict(project, persist_defaults=False)
    merged_input = {**current, **(partial or {})}
    if "reject_threshold" in (partial or {}) and isinstance(partial.get("reject_threshold"), dict):
        merged_input["reject_threshold"] = {
            **(current.get("reject_threshold") or {}),
            **partial["reject_threshold"],
        }
    policy = normalize_gate_policy(merged_input)
    errors, warnings = validate_gate_policy(policy)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos de la política; no se pudo guardar.",
            errors=errors,
            warnings=warnings,
        )

    try:
        _write_policy(project, policy)
    except Exception:
        logger.exception("save_gate_policy unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Política de validación guardada correctamente.",
        payload={
            "gate_policy": policy,
            "warnings": warnings,
            "warning_messages": source_persistence_service.flatten_validation_messages(warnings),
        },
    )


def ensure_policy_for_publish(project: Project) -> tuple[dict, dict[str, list[str]], dict[str, list[str]]]:
    """Materializa defaults si faltan y valida antes de publicar el contrato."""
    policy = get_policy_dict(project, persist_defaults=True)
    errors, warnings = validate_gate_policy(policy)
    return policy, errors, warnings


def step_statuses(policy: dict) -> list[str]:
    """done | draft | pending para pasos 1–3."""
    errors, _warnings = validate_gate_policy(policy)
    collection_ok = not any(
        key in errors for key in ("on_error", "abort_on_first_fatal", "max_errors")
    )
    threshold_ok = not any(
        key in errors for key in ("reject_threshold_mode", "reject_threshold_value")
    )
    if collection_ok:
        s1 = "done"
    else:
        s1 = "draft"
    if threshold_ok:
        s2 = "done"
    elif collection_ok:
        s2 = "draft"
    else:
        s2 = "pending"
    if collection_ok and threshold_ok:
        s3 = "done"
    elif threshold_ok or collection_ok:
        s3 = "draft"
    else:
        s3 = "pending"
    return [s1, s2, s3]


def threshold_summary(policy: dict) -> str:
    threshold = policy.get("reject_threshold") or {}
    mode = threshold.get("mode")
    value = threshold.get("value")
    if mode == THRESHOLD_MODE_PERCENT:
        return f"{value}%"
    if mode == THRESHOLD_MODE_COUNT:
        return f"{value} filas"
    return "—"


def collection_summary(policy: dict) -> str:
    return f"{policy.get('on_error', '—')} · max {policy.get('max_errors', '—')}"


@dataclass
class PolicyWizardStep:
    number: int
    slug: str
    title: str
    summary: str
    status: str
    url_name: str


@dataclass
class PolicyWizardContext:
    project_name: str
    project_slug: str
    membership_role: str = "—"
    version_label: str = "Borrador"
    steps_complete: int = 0
    steps_total: int = 3
    policy: dict = field(default_factory=default_gate_policy)
    steps: list[PolicyWizardStep] = field(default_factory=list)
    continue_step_url_name: str = "file_gate:policy_step1"
    threshold_label: str = "—"
    collection_label: str = "—"
    is_complete: bool = False


def get_wizard_context(project, membership=None) -> PolicyWizardContext:
    policy = get_policy_dict(project, persist_defaults=True)
    version = source_persistence_service.get_draft_version(project)
    role = membership.role if membership else "—"
    statuses = step_statuses(policy)

    steps = [
        PolicyWizardStep(
            1,
            "paso-1",
            "Paso 1 — Recolección y corte",
            collection_summary(policy),
            statuses[0],
            "file_gate:policy_step1",
        ),
        PolicyWizardStep(
            2,
            "paso-2",
            "Paso 2 — Umbral de rechazo",
            threshold_summary(policy),
            statuses[1],
            "file_gate:policy_step2",
        ),
        PolicyWizardStep(
            3,
            "paso-3",
            "Paso 3 — Revisión",
            "Snapshot listo para publicar con el contrato"
            if statuses[2] == "done"
            else "Revise la decisión del gate",
            statuses[2],
            "file_gate:policy_step3",
        ),
    ]
    done = sum(1 for step in steps if step.status == "done")
    continue_url = "file_gate:policy_step1"
    for step in steps:
        if step.status != "done":
            continue_url = step.url_name
            break

    return PolicyWizardContext(
        project_name=project.name,
        project_slug=project.slug,
        membership_role=role,
        version_label=f"Borrador v{version.version_number}",
        steps_complete=done,
        steps_total=3,
        policy=policy,
        steps=steps,
        continue_step_url_name=continue_url,
        threshold_label=threshold_summary(policy),
        collection_label=collection_summary(policy),
        is_complete=done >= 3,
    )


def evaluate_threshold_preview(
    *,
    mode: str,
    threshold_value: float | int,
    rows_evaluated: int,
    rows_rejected: int,
) -> dict:
    """Simulador UI — misma semántica `>` del documento."""
    rows_evaluated = max(0, int(rows_evaluated))
    rows_rejected = max(0, int(rows_rejected))
    if mode == THRESHOLD_MODE_PERCENT:
        measured = (rows_rejected / rows_evaluated) * 100 if rows_evaluated else 0.0
    else:
        measured = float(rows_rejected)
    failed = measured > float(threshold_value)
    return {
        "measured": measured,
        "failed": failed,
        "status": "failed" if failed else "passed",
    }
