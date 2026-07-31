"""PROFILE_SEED — permisos, hub (M1) y selector de origen (M2)."""

from __future__ import annotations

from apps.dms.file_intake.services import file_intake_persistence_service
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.file_gate.projects.services import gate_project_service
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

MSG_NO_IMPORT = "No tiene permiso para importar estructuras en este proyecto."
MSG_NO_ACCESS_MATCH = "No tiene acceso a este proyecto FILE MATCH."
MSG_SOURCE_UNAVAILABLE = (
    "El origen seleccionado no está disponible o no tiene versión publicada."
)
MSG_KIND_UNSUPPORTED = "Este tipo de origen aún no está disponible para importar."
MSG_NO_SOURCES = (
    "No hay orígenes publicados visibles. "
    "Publique un esquema en FILE GATE o pida acceso a un proyecto GATE."
)

TARGET_SLOT_PROFILE_A = "profile_a"
TARGET_SLOT_LABEL_PROFILE_A = "Perfil A (archivo A)"

SOURCE_KIND_FILE_GATE = Project.KIND_FILE_GATE
SOURCE_SLOT_SCHEMA = "schema"
SOURCE_SLOT_LABEL_SCHEMA = "Esquema"

SOURCE_KIND_CHOICES_P0 = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
)


def user_can_import(user, target_project: Project) -> bool:
    """PA/ED on the destination project may open Importar estructura (H1)."""
    if target_project is None:
        return False
    if target_project.is_archived:
        return False
    if target_project.project_kind != Project.KIND_FILE_MATCH:
        return False
    membership = project_service.get_membership(user, target_project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
    )


def get_profile_a_seed_context(user, target_project: Project) -> dict:
    """Shell context for Match Perfil A import entry (M1)."""
    can_import = user_can_import(user, target_project)
    return {
        "can_seed_import": can_import,
        "target_kind": Project.KIND_FILE_MATCH,
        "target_kind_label": "FILE MATCH",
        "target_slot": TARGET_SLOT_PROFILE_A,
        "target_slot_label": TARGET_SLOT_LABEL_PROFILE_A,
        "seed_step": 1,
        "seed_steps_total": 3,
    }


def _source_row_from_gate(project: Project) -> dict | None:
    published = file_intake_persistence_service.get_published_version(project)
    if published is None:
        return None
    profile = published.source_profile
    if profile is None:
        return None
    source = source_persistence_service.profile_to_dict(profile)
    fields = source.get("fields") or []
    version_number = published.version_number
    return {
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "kind": SOURCE_KIND_FILE_GATE,
        "kind_label": "FILE GATE",
        "slot": SOURCE_SLOT_SCHEMA,
        "slot_label": SOURCE_SLOT_LABEL_SCHEMA,
        "version_number": version_number,
        "version_label": f"v{version_number}",
        "file_type_code": source.get("file_type_code") or "—",
        "fields_count": len(fields),
        "published_at": published.published_at,
    }


def list_eligible_sources(
    user,
    target_project: Project,
    source_kind: str = SOURCE_KIND_FILE_GATE,
) -> list[dict]:
    """Published origins visible to user for seeding into target (M2 P0: GATE)."""
    if target_project is None:
        return []
    if source_kind != SOURCE_KIND_FILE_GATE:
        return []

    qs = (
        gate_project_service.visible_projects_qs(user)
        .filter(
            is_archived=False,
            company_id=target_project.company_id,
            dms_config__current_version__status=DmsMappingVersion.STATUS_PUBLISHED,
        )
        .select_related(
            "dms_config",
            "dms_config__current_version",
            "dms_config__current_version__source_profile",
        )
        .order_by("slug")
    )

    rows: list[dict] = []
    for project in qs:
        row = _source_row_from_gate(project)
        if row is not None:
            rows.append(row)
    return rows


def get_source_picker_context(
    user,
    target_project: Project,
    *,
    source_kind: str | None = None,
    source_id: int | None = None,
) -> dict:
    """Context for Match Perfil A origin picker (M2)."""
    base = get_profile_a_seed_context(user, target_project)
    kind = (source_kind or SOURCE_KIND_FILE_GATE).strip() or SOURCE_KIND_FILE_GATE
    kind_supported = kind == SOURCE_KIND_FILE_GATE
    sources = (
        list_eligible_sources(user, target_project, source_kind=kind)
        if kind_supported
        else []
    )

    selected = None
    invalid_source = False
    if source_id is not None:
        selected = next((row for row in sources if row["id"] == source_id), None)
        if selected is None:
            invalid_source = True

    return {
        **base,
        "seed_step": 2,
        "source_kind": kind,
        "source_kind_choices": SOURCE_KIND_CHOICES_P0,
        "source_kind_supported": kind_supported,
        "sources": sources,
        "selected_source": selected,
        "selected_source_id": selected["id"] if selected else None,
        "invalid_source": invalid_source,
        "has_sources": bool(sources),
        "msg_no_sources": MSG_NO_SOURCES,
        "msg_kind_unsupported": MSG_KIND_UNSUPPORTED,
    }
