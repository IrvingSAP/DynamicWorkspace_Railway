"""Contexto del asistente de contrato de salida (output_definition.md)."""

from dataclasses import dataclass, field

from apps.dms.target_profile.services import target_profile_catalog_service, target_profile_service
from apps.reverse_studio.output.services.output_whitelist import OUTPUT_FILE_TYPE_WHITELIST


@dataclass
class WizardStepStatus:
    number: int
    slug: str
    title: str
    summary: str
    status: str
    url_name: str


@dataclass
class OutputWizardContext:
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
    continue_step_url_name: str = "reverse_studio:output_step1"


_STEP_META = (
    (1, "paso-1", "Paso 1 — Tipo de layout", "reverse_studio:output_step1"),
    (2, "paso-2", "Paso 2 — Codificación de salida", "reverse_studio:output_step2"),
    (3, "paso-3", "Paso 3 — Estructura del archivo", "reverse_studio:output_step3"),
    (4, "paso-4", "Paso 4 — Campos del layout", "reverse_studio:output_step4"),
    (5, "paso-5", "Paso 5 — Serialización", "reverse_studio:output_step5"),
    (6, "paso-6", "Paso 6 — Validación al escribir", "reverse_studio:output_step6"),
)


def get_wizard_context(project, membership=None) -> OutputWizardContext:
    base = target_profile_service.get_wizard_context(project, membership)
    steps = []
    for meta, base_step in zip(_STEP_META, base.steps):
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
    continue_url = "reverse_studio:output_step1"
    for step in steps:
        if step.status != "done":
            continue_url = step.url_name
            break
    return OutputWizardContext(
        project_name=base.project_name,
        project_slug=base.project_slug,
        membership_role=base.membership_role,
        version_label=base.version_label,
        version_number=base.version_number,
        steps_complete=base.steps_complete,
        steps_total=base.steps_total,
        file_type_label=base.file_type_label,
        fields_count=base.fields_count,
        steps=steps,
        continue_step_url_name=continue_url,
    )


def get_step1_catalog_context() -> dict:
    ctx = target_profile_catalog_service.get_step1_catalog_context()
    file_types = [
        item
        for item in (ctx.get("file_types") or [])
        if item.get("code") in OUTPUT_FILE_TYPE_WHITELIST
    ]
    ctx["file_types"] = file_types
    ctx["output_whitelist"] = sorted(OUTPUT_FILE_TYPE_WHITELIST)
    return ctx
