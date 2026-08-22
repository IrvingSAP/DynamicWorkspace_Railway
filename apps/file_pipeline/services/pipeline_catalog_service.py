"""CRUD y lectura del Pipeline Step Catalog (M2b)."""

from __future__ import annotations

import logging
import re

from django.db.models import Q

from apps.company.models import Company
from apps.core.services.operation_result import OperationResult
from apps.file_pipeline.models import (
    PipelineCompanyKindFlag,
    PipelineDefinition,
    PipelineStepKind,
)

logger = logging.getLogger(__name__)

KIND_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

MSG_UA_ONLY = "Solo un operador de plataforma puede gestionar el catálogo de pasos."
MSG_CREATED = "Kind registrado en el catálogo."
MSG_UPDATED = "Kind actualizado."
MSG_DISABLED = "Kind deshabilitado. Ya no se ofrece en nuevos diseños."
MSG_FLAG = "Paquete de compañía actualizado."
MSG_VALIDATION = "Revise los datos marcados; no se pudo guardar."
MSG_CONFLICT = "No combine pipeline_enabled activo con status disabled."
MSG_NOT_FOUND = "No se encontró esa entrada del catálogo."

INPUT_CHOICES = PipelineStepKind.INPUT_CHOICES
OUTPUT_CHOICES = PipelineStepKind.OUTPUT_CHOICES

SEED_ROWS = (
    {
        "kind": "file_clean",
        "label": "File Clean",
        "short_label": "Clean",
        "description": "Normalización / limpieza antes de Gate u otros pasos.",
        "project_kind": "file_clean",
        "runner": "run_clean_job",
        "input_arity": "1",
        "output_arity": "1",
        "produces_file": True,
        "pipeline_enabled": True,
        "mvp_phase": "A",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "file_gate",
        "label": "File Gate",
        "short_label": "Gate",
        "description": "Validación de archivo; veredicto e informe.",
        "project_kind": "file_gate",
        "runner": "run_file_gate_job",
        "input_arity": "1",
        "output_arity": "1",
        "produces_file": True,
        "pipeline_enabled": True,
        "mvp_phase": "A",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "file_split",
        "label": "File Split",
        "short_label": "Split",
        "description": "Parte un archivo en N salidas.",
        "project_kind": "file_split_merge",
        "runner": "run_sm_job",
        "input_arity": "1",
        "output_arity": "N",
        "produces_file": True,
        "pipeline_enabled": True,
        "mvp_phase": "A",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "file_merge",
        "label": "File Merge",
        "short_label": "Merge",
        "description": "Consolida N archivos en uno.",
        "project_kind": "file_split_merge",
        "runner": "run_sm_job",
        "input_arity": "N",
        "output_arity": "1",
        "produces_file": True,
        "pipeline_enabled": True,
        "mvp_phase": "A",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "dms",
        "label": "FilePipe",
        "short_label": "Pipe",
        "description": "Transformación FilePipe (versión publicada del proyecto).",
        "project_kind": "dms",
        "runner": "run_full_job",
        "input_arity": "1",
        "output_arity": "1",
        "produces_file": True,
        "pipeline_enabled": True,
        "mvp_phase": "A",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "reverse",
        "label": "Reverse Studio",
        "short_label": "Reverse",
        "description": "Emisión / layout a partir de un archivo.",
        "project_kind": "reverse",
        "runner": "run_reverse_job",
        "input_arity": "1",
        "output_arity": "1",
        "produces_file": True,
        "pipeline_enabled": True,
        "mvp_phase": "B",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "file_match",
        "label": "File Match",
        "short_label": "Match",
        "description": "Conciliación A/B; informe.",
        "project_kind": "file_match",
        "runner": "run_file_match_job",
        "input_arity": "2",
        "output_arity": "none",
        "produces_file": False,
        "pipeline_enabled": True,
        "mvp_phase": "B",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "structure_scout",
        "label": "Structure Scout",
        "short_label": "Scout",
        "description": "Exploración de estructura; uso limitado en cadena.",
        "project_kind": "structure_scout",
        "runner": "run_structure_scout_job",
        "input_arity": "1",
        "output_arity": "none",
        "produces_file": False,
        "pipeline_enabled": False,
        "mvp_phase": "C",
        "status": PipelineStepKind.STATUS_ACTIVE,
    },
    {
        "kind": "file_repair",
        "label": "File Repair",
        "short_label": "Repair",
        "description": "Reparación asistida tras Gate. Pendiente de checklist.",
        "project_kind": "file_repair",
        "runner": "run_file_repair_job",
        "input_arity": "1",
        "output_arity": "1",
        "produces_file": True,
        "pipeline_enabled": False,
        "mvp_phase": "",
        "status": PipelineStepKind.STATUS_DISABLED,
    },
)


def seed_catalog() -> int:
    created = 0
    for row in SEED_ROWS:
        _, was = PipelineStepKind.objects.get_or_create(
            kind=row["kind"],
            defaults=row,
        )
        if was:
            created += 1
    return created


def _is_ua(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.user_type == "UA")


def _blocked_kinds_for_company(company) -> set[str]:
    if company is None:
        return set()
    return set(
        PipelineCompanyKindFlag.objects.filter(
            company=company,
            included=False,
        ).values_list("step_kind__kind", flat=True)
    )


def enabled_kinds(company=None) -> list[dict]:
    blocked = _blocked_kinds_for_company(company)
    qs = (
        PipelineStepKind.objects.filter(pipeline_enabled=True)
        .exclude(status=PipelineStepKind.STATUS_DISABLED)
        .order_by("kind")
    )
    return [row.as_picker_dict() for row in qs if row.kind not in blocked]


def get_kind(kind: str, company=None) -> dict | None:
    if not kind:
        return None
    try:
        row = PipelineStepKind.objects.get(kind=kind)
    except PipelineStepKind.DoesNotExist:
        return None
    if not row.pipeline_enabled or row.status == PipelineStepKind.STATUS_DISABLED:
        return None
    if kind in _blocked_kinds_for_company(company):
        return None
    return row.as_picker_dict()


def short_label(kind: str) -> str:
    row = PipelineStepKind.objects.filter(kind=kind).first()
    if row:
        return row.short
    return kind


def get_row(kind: str) -> PipelineStepKind | None:
    return PipelineStepKind.objects.filter(kind=kind).first()


def catalog_stats() -> dict:
    qs = PipelineStepKind.objects.all()
    total = qs.count()
    enabled = qs.filter(pipeline_enabled=True).exclude(
        status=PipelineStepKind.STATUS_DISABLED
    ).count()
    return {
        "total": total,
        "enabled": enabled,
        "off": total - enabled,
        "phase_a": qs.filter(mvp_phase="A").count(),
    }


def list_kinds(q: str = "", enabled: str = "all", phase: str = "all"):
    qs = PipelineStepKind.objects.all()
    term = (q or "").strip()
    if term:
        qs = qs.filter(
            Q(kind__icontains=term)
            | Q(label__icontains=term)
            | Q(project_kind__icontains=term)
            | Q(runner__icontains=term)
        )
    if enabled == "on":
        qs = qs.filter(pipeline_enabled=True).exclude(
            status=PipelineStepKind.STATUS_DISABLED
        )
    elif enabled == "off":
        qs = qs.filter(
            Q(pipeline_enabled=False) | Q(status=PipelineStepKind.STATUS_DISABLED)
        )
    if phase == "-":
        qs = qs.filter(mvp_phase="")
    elif phase in {"A", "B", "C"}:
        qs = qs.filter(mvp_phase=phase)
    return list(qs)


def default_posted() -> dict:
    return {
        "kind": "",
        "label": "",
        "short_label": "",
        "description": "",
        "project_kind": "",
        "runner": "",
        "input_arity": "1",
        "output_arity": "1",
        "produces_file": "0",
        "pipeline_enabled": "0",
        "mvp_phase": "",
        "status": PipelineStepKind.STATUS_ACTIVE,
    }


def posted_from_request(post, *, include_kind: bool) -> dict:
    posted = {
        "label": post.get("label", "").strip(),
        "short_label": post.get("short_label", "").strip(),
        "description": post.get("description", "").strip(),
        "project_kind": post.get("project_kind", "").strip().lower(),
        "runner": post.get("runner", "").strip(),
        "input_arity": post.get("input_arity", "1").strip(),
        "output_arity": post.get("output_arity", "1").strip(),
        "produces_file": "1" if post.get("produces_file") else "0",
        "pipeline_enabled": "1" if post.get("pipeline_enabled") == "1" else "0",
        "mvp_phase": post.get("mvp_phase", "").strip(),
        "status": post.get("status", PipelineStepKind.STATUS_ACTIVE).strip(),
    }
    if include_kind:
        posted["kind"] = post.get("kind", "").strip().lower()
    return posted


def posted_from_row(row: PipelineStepKind) -> dict:
    return {
        "kind": row.kind,
        "label": row.label,
        "short_label": row.short_label,
        "description": row.description,
        "project_kind": row.project_kind,
        "runner": row.runner,
        "input_arity": row.input_arity,
        "output_arity": row.output_arity,
        "produces_file": "1" if row.produces_file else "0",
        "pipeline_enabled": "1" if row.pipeline_enabled else "0",
        "mvp_phase": row.mvp_phase,
        "status": row.status,
    }


def _validate_posted(posted: dict, *, kind_required: bool) -> dict:
    errors: dict[str, list[str]] = {}
    if kind_required:
        kind = posted.get("kind", "")
        if not kind:
            errors["kind"] = ["Indique el código kind."]
        elif not KIND_RE.match(kind):
            errors["kind"] = ["Use minúsculas, números y guion bajo; empiece por letra."]
        elif PipelineStepKind.objects.filter(kind=kind).exists():
            errors["kind"] = ["Ya existe un kind con ese código."]
    if not posted.get("label"):
        errors["label"] = ["Indique el label."]
    if not posted.get("project_kind"):
        errors["project_kind"] = ["Indique el project_kind."]
    elif not KIND_RE.match(posted["project_kind"]):
        errors["project_kind"] = ["project_kind no es válido."]
    if not posted.get("runner"):
        errors["runner"] = ["Indique el runner."]
    if posted.get("input_arity") not in dict(PipelineStepKind.INPUT_CHOICES):
        errors["input_arity"] = ["input_arity no es válido."]
    if posted.get("output_arity") not in dict(PipelineStepKind.OUTPUT_CHOICES):
        errors["output_arity"] = ["output_arity no es válido."]
    if posted.get("mvp_phase") not in {"", "A", "B", "C"}:
        errors["mvp_phase"] = ["Fase no válida."]
    if posted.get("status") not in dict(PipelineStepKind.STATUS_CHOICES):
        errors["status"] = ["Status no válido."]
    enabled = posted.get("pipeline_enabled") == "1"
    if enabled and posted.get("status") == PipelineStepKind.STATUS_DISABLED:
        errors["status"] = [MSG_CONFLICT]
        errors.setdefault("pipeline_enabled", []).append(MSG_CONFLICT)
    return errors


def _apply_posted(row: PipelineStepKind, posted: dict, user) -> None:
    row.label = posted["label"][:120]
    row.short_label = (posted.get("short_label") or "")[:40]
    row.description = posted.get("description") or ""
    row.project_kind = posted["project_kind"][:64]
    row.runner = posted["runner"][:120]
    row.input_arity = posted["input_arity"]
    row.output_arity = posted["output_arity"]
    row.produces_file = posted.get("produces_file") == "1"
    row.pipeline_enabled = posted.get("pipeline_enabled") == "1"
    row.mvp_phase = posted.get("mvp_phase") or ""
    row.status = posted["status"]
    row.updated_by = user


def create_kind(user, posted: dict) -> OperationResult:
    if not _is_ua(user):
        return OperationResult.failure("forbidden", MSG_UA_ONLY)
    errors = _validate_posted(posted, kind_required=True)
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)
    row = PipelineStepKind(kind=posted["kind"])
    _apply_posted(row, posted, user)
    try:
        row.save()
    except Exception:
        logger.exception("create_pipeline_step_kind")
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_CREATED, payload={"row": row})


def update_kind(user, row: PipelineStepKind, posted: dict) -> OperationResult:
    if not _is_ua(user):
        return OperationResult.failure("forbidden", MSG_UA_ONLY)
    errors = _validate_posted(posted, kind_required=False)
    if errors:
        return OperationResult.failure("validation_form", MSG_VALIDATION, errors=errors)
    _apply_posted(row, posted, user)
    try:
        row.save()
    except Exception:
        logger.exception("update_pipeline_step_kind kind=%s", row.kind)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_UPDATED, payload={"row": row})


def count_draft_references(kind: str) -> int:
    n = 0
    for pipeline in PipelineDefinition.objects.exclude(draft_steps=[]).iterator():
        steps = pipeline.draft_steps or []
        if any(isinstance(s, dict) and s.get("kind") == kind for s in steps):
            n += 1
    return n


def disable_kind(user, row: PipelineStepKind, reason: str) -> OperationResult:
    if not _is_ua(user):
        return OperationResult.failure("forbidden", MSG_UA_ONLY)
    row.pipeline_enabled = False
    row.status = PipelineStepKind.STATUS_DISABLED
    row.disable_reason = (reason or "").strip()[:255]
    row.updated_by = user
    try:
        row.save(
            update_fields=[
                "pipeline_enabled",
                "status",
                "disable_reason",
                "updated_by",
                "updated_at",
            ]
        )
    except Exception:
        logger.exception("disable_pipeline_step_kind kind=%s", row.kind)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )
    return OperationResult.success(user_message=MSG_DISABLED, payload={"row": row})


def company_kind_matrix(company: Company) -> list[dict]:
    blocked = _blocked_kinds_for_company(company)
    rows = []
    for item in PipelineStepKind.objects.order_by("kind"):
        catalog_on = item.pipeline_enabled and item.status != PipelineStepKind.STATUS_DISABLED
        pkg = item.kind not in blocked
        rows.append(
            {
                "row": item,
                "catalog_on": catalog_on,
                "package_included": pkg,
                "in_designer": catalog_on and pkg,
            }
        )
    return rows


def set_company_flag(user, company: Company, kind: str, included: bool) -> OperationResult:
    if not _is_ua(user):
        return OperationResult.failure("forbidden", MSG_UA_ONLY)
    row = get_row(kind)
    if row is None:
        return OperationResult.failure("not_found", MSG_NOT_FOUND)
    flag, _ = PipelineCompanyKindFlag.objects.get_or_create(
        company=company,
        step_kind=row,
        defaults={"included": included},
    )
    flag.included = included
    flag.save(update_fields=["included", "updated_at"])
    return OperationResult.success(user_message=MSG_FLAG)
