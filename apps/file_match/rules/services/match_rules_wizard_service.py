"""Contexto UI del hub / secciones de reglas de cruce."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.profile_a.services import profile_a_wizard_service
from apps.file_match.profile_b.services import profile_b_wizard_service
from apps.file_match.rules.services import match_rules_persistence_service


@dataclass
class RulesSectionStatus:
    slug: str
    title: str
    summary: str
    status: str  # done | draft | pending
    url_name: str


@dataclass
class MatchRulesContext:
    project_name: str
    project_slug: str
    membership_role: str = "—"
    version_label: str = "Borrador"
    version_number: int = 1
    key_count: int = 0
    compare_count: int = 0
    normalize_label: str = "—"
    rules_complete: bool = False
    profile_a_complete: bool = False
    profile_b_complete: bool = False
    sections: list[RulesSectionStatus] = field(default_factory=list)
    continue_section_url_name: str = "file_match:rules_keys"
    rules: dict = field(default_factory=dict)
    rules_json: str = "{}"
    fields_a: list[str] = field(default_factory=list)
    fields_b: list[str] = field(default_factory=list)


def get_rules_context(project, membership=None) -> MatchRulesContext:
    rules = match_rules_persistence_service.get_rules_dict(project)
    version = source_persistence_service.get_or_create_draft_version(project)
    role = membership.role if membership else "—"

    a_wiz = profile_a_wizard_service.get_wizard_context(project, membership)
    b_wiz = profile_b_wizard_service.get_wizard_context(project, membership)
    profile_a_complete = a_wiz.steps_complete >= a_wiz.steps_total
    profile_b_complete = b_wiz.steps_complete >= b_wiz.steps_total

    key = rules.get("key") or []
    compare = rules.get("compare") or []
    norm = rules.get("normalize") or {}
    parts = []
    if norm.get("trim"):
        parts.append("trim")
    if norm.get("case_fold_keys"):
        parts.append("case")
    normalize_label = " · ".join(parts) if parts else "off"

    key_status = "done" if key else "pending"
    compare_status = "done" if compare else ("draft" if key else "pending")
    normalize_status = "done" if key else "pending"

    sections = [
        RulesSectionStatus(
            "claves",
            "1 · Claves de cruce",
            _pairs_summary(key) or "Sin pares de clave",
            key_status,
            "file_match:rules_keys",
        ),
        RulesSectionStatus(
            "comparar",
            "2 · Campos a comparar",
            _pairs_summary(compare) or "Solo presencia (sin compare)",
            compare_status,
            "file_match:rules_compare",
        ),
        RulesSectionStatus(
            "normalizacion",
            "3 · Normalización",
            normalize_label,
            normalize_status,
            "file_match:rules_normalize",
        ),
    ]

    continue_url = "file_match:rules_keys"
    for section in sections:
        if section.status != "done":
            continue_url = section.url_name
            break

    return MatchRulesContext(
        project_name=project.name,
        project_slug=project.slug,
        membership_role=role,
        version_label=f"Borrador v{version.version_number}",
        version_number=version.version_number,
        key_count=len(key),
        compare_count=len(compare),
        normalize_label=normalize_label,
        rules_complete=bool(key),
        profile_a_complete=profile_a_complete,
        profile_b_complete=profile_b_complete,
        sections=sections,
        continue_section_url_name=continue_url,
        rules=rules,
        rules_json=json.dumps(rules, indent=2, ensure_ascii=False),
        fields_a=match_rules_persistence_service.field_names_a(project),
        fields_b=match_rules_persistence_service.field_names_b(project),
    )


def _pairs_summary(pairs: list[dict]) -> str:
    if not pairs:
        return ""
    bits = []
    for pair in pairs[:3]:
        bits.append(f"{pair.get('a')} ↔ {pair.get('b')}")
    extra = len(pairs) - 3
    text = ", ".join(bits)
    if extra > 0:
        text += f" (+{extra})"
    return text
