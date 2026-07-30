"""Contexto del asistente de perfil B (profile_b.md)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from apps.dms.source_profile.services import (
    source_persistence_service,
    source_profile_catalog_service,
    source_profile_service,
)
from apps.file_match.profile_b.services import profile_b_persistence_service
from apps.file_match.profile_b.services.profile_b_whitelist import PROFILE_B_FILE_TYPE_WHITELIST


@dataclass
class WizardStepStatus:
    number: int
    slug: str
    title: str
    summary: str
    status: str
    url_name: str


@dataclass
class ProfileBWizardContext:
    project_name: str
    project_slug: str
    membership_role: str = "—"
    version_label: str = "Borrador"
    version_number: int = 1
    steps_complete: int = 0
    steps_total: int = 6
    file_type_label: str = "—"
    fields_count: int = 0
    steps: list[WizardStepStatus] = field(default_factory=list)
    continue_step_url_name: str = "file_match:profile_b_step1"
    profile_a_complete: bool = False


_STEP_META = (
    (1, "paso-1", "Paso 1 — Tipo de archivo B", "file_match:profile_b_step1"),
    (2, "paso-2", "Paso 2 — Inicio de captura", "file_match:profile_b_step2"),
    (3, "paso-3", "Paso 3 — Fin de captura", "file_match:profile_b_step3"),
    (4, "paso-4", "Paso 4 — Campos del archivo B", "file_match:profile_b_step4"),
    (5, "paso-5", "Paso 5 — Reglas de contenido", "file_match:profile_b_step5"),
    (6, "paso-6", "Paso 6 — Informe de lectura", "file_match:profile_b_step6"),
)


def get_wizard_context(project, membership=None) -> ProfileBWizardContext:
    source = profile_b_persistence_service.get_source_b_dict(project)
    version = source_persistence_service.get_or_create_draft_version(project)
    role = membership.role if membership else "—"
    statuses = source_persistence_service.step_statuses(source)

    # Reuse A wizard summaries via DMS base (same summaries from source dict)
    base = source_profile_service.get_wizard_context(project, membership)
    # Override summaries using B source by temporarily computing via step helpers
    from apps.dms.source_profile.services.source_profile_service import (
        _capture_end_summary,
        _capture_start_summary,
        _fields_summary,
        _report_summary,
        _rules_summary,
    )

    summaries = [
        source_persistence_service.file_type_label(source.get("file_type_code", "")),
        _capture_start_summary(source.get("capture_start") or {}),
        _capture_end_summary(source.get("capture_end") or {}),
        _fields_summary(source.get("fields") or []),
        _rules_summary(source.get("content_rules") or {}),
        _report_summary(source.get("processing_report") or {}),
    ]

    steps = []
    for meta, status, summary in zip(_STEP_META, statuses, summaries):
        number, slug, title, url_name = meta
        steps.append(WizardStepStatus(number, slug, title, summary, status, url_name))

    continue_url = "file_match:profile_b_step1"
    for step in steps:
        if step.status != "done":
            continue_url = step.url_name
            break

    profile_a_complete = base.steps_complete >= base.steps_total
    fields = source.get("fields") or []
    return ProfileBWizardContext(
        project_name=project.name,
        project_slug=project.slug,
        membership_role=role,
        version_label=f"Borrador v{version.version_number}",
        version_number=version.version_number,
        steps_complete=sum(1 for step in steps if step.status == "done"),
        steps_total=6,
        file_type_label=source_persistence_service.file_type_label(
            source.get("file_type_code", "")
        ),
        fields_count=len(fields),
        steps=steps,
        continue_step_url_name=continue_url,
        profile_a_complete=profile_a_complete,
    )


def get_step1_catalog_context() -> dict:
    ctx = source_profile_catalog_service.get_step1_catalog_context()
    file_types = [
        item
        for item in (ctx.get("file_types") or [])
        if (item.get("code") if isinstance(item, dict) else getattr(item, "code", None))
        in PROFILE_B_FILE_TYPE_WHITELIST
    ]
    ctx["file_types"] = file_types
    ctx["profile_b_whitelist"] = sorted(PROFILE_B_FILE_TYPE_WHITELIST)
    return ctx


def get_step4_context(project, variant: str | None = None) -> dict:
    from apps.dms.source_profile.services.source_profile_service import (
        default_config_for_type,
        default_fields_for_type,
        get_content_type_choices,
        get_step4_variant,
    )

    source = profile_b_persistence_service.ensure_step4_coherence_b(project)
    file_type = source.get("file_type_code", "")
    resolved = variant or get_step4_variant(file_type)
    fields = source.get("fields") or default_fields_for_type(file_type)
    config = default_config_for_type(file_type, source.get("config") or {})
    return {
        "step4_variant": resolved,
        "file_type_code": file_type,
        "fields_json": json.dumps(fields),
        "fields_count": len(fields),
        "config_json": json.dumps(config),
        "content_types": get_content_type_choices(),
    }


def get_step5_content_rules_context(project) -> dict:
    from apps.dms.source_profile.services.source_profile_service import DEFAULT_CONTENT_RULES

    source = profile_b_persistence_service.get_source_b_dict(project)
    rules = {**DEFAULT_CONTENT_RULES, **(source.get("content_rules") or {})}
    return {"content_rules_json": json.dumps(rules)}


def get_step6_report_context(project) -> dict:
    from apps.dms.source_profile.services.source_profile_service import DEFAULT_PROCESSING_REPORT

    source = profile_b_persistence_service.get_source_b_dict(project)
    report = source.get("processing_report") or DEFAULT_PROCESSING_REPORT
    return {"processing_report_json": json.dumps(report)}
