"""Wizard context for File Split/Merge read profile (4 steps; no Gate content rules)."""

from dataclasses import dataclass, field

from apps.dms.source_profile.services import source_profile_service


@dataclass
class WizardStepStatus:
    number: int
    slug: str
    title: str
    summary: str
    status: str  # done | draft | pending
    url_name: str


@dataclass
class ProfileWizardContext:
    project_name: str
    project_slug: str
    membership_role: str = "—"
    version_label: str = "Borrador"
    version_number: int = 1
    steps_complete: int = 0
    steps_total: int = 4
    file_type_label: str = "—"
    fields_count: int = 0
    steps: list[WizardStepStatus] = field(default_factory=list)
    continue_step_url_name: str = "file_split_merge:profile_step1"


_STEP_META = (
    (1, "paso-1", "Paso 1 — Tipo de archivo", "file_split_merge:profile_step1"),
    (2, "paso-2", "Paso 2 — Inicio de captura", "file_split_merge:profile_step2"),
    (3, "paso-3", "Paso 3 — Fin de captura", "file_split_merge:profile_step3"),
    (4, "paso-4", "Paso 4 — Campos del perfil", "file_split_merge:profile_step4"),
)


def get_wizard_context(project, membership=None) -> ProfileWizardContext:
    base = source_profile_service.get_wizard_context(project, membership)
    steps = []
    for meta, base_step in zip(_STEP_META, base.steps[:4]):
        number, slug, title, url_name = meta
        steps.append(
            WizardStepStatus(
                number,
                slug,
                title,
                base_step.summary,
                base_step.status,
                url_name,
            )
        )
    steps_complete = sum(1 for step in steps if step.status == "done")
    continue_url = "file_split_merge:profile_step1"
    for step in steps:
        if step.status != "done":
            continue_url = step.url_name
            break
    else:
        continue_url = "file_split_merge:profile_hub"

    return ProfileWizardContext(
        project_name=base.project_name,
        project_slug=base.project_slug,
        membership_role=base.membership_role,
        version_label=base.version_label,
        version_number=base.version_number,
        steps_complete=steps_complete,
        steps_total=4,
        file_type_label=base.file_type_label,
        fields_count=base.fields_count,
        steps=steps,
        continue_step_url_name=continue_url,
    )
