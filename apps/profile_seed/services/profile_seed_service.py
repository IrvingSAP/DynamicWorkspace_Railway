"""PROFILE_SEED — permisos, hub y selector de origen (Match A + Split/Merge)."""

from __future__ import annotations

from uuid import UUID

from apps.dms.file_intake.services import file_intake_persistence_service
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.file_clean.projects.services import clean_project_service
from apps.file_gate.projects.services import gate_project_service
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import project_service

MSG_NO_IMPORT = "No tiene permiso para importar estructuras en este proyecto."
MSG_SOURCE_UNAVAILABLE = (
    "El origen seleccionado no está disponible o no tiene versión publicada."
)
MSG_KIND_UNSUPPORTED = "Este tipo de origen aún no está disponible para importar."
MSG_NO_SOURCES_GATE = (
    "No hay orígenes FILE GATE publicados visibles. "
    "Publique un esquema en FILE GATE o pida acceso a un proyecto GATE."
)
MSG_NO_SOURCES_CLEAN = (
    "No hay orígenes FILE CLEAN publicados visibles. "
    "Publique un perfil en FILE CLEAN o pida acceso a un proyecto Clean."
)
# Compatibilidad con callers Match existentes
MSG_NO_SOURCES = MSG_NO_SOURCES_GATE
MSG_NO_ACCESS_MATCH = "No tiene acceso a este proyecto FILE MATCH."

TARGET_SLOT_PROFILE_A = "profile_a"
TARGET_SLOT_LABEL_PROFILE_A = "Perfil A (archivo A)"
TARGET_SLOT_READ_PROFILE = "read_profile"
TARGET_SLOT_LABEL_READ_PROFILE = "Perfil de lectura"

SOURCE_KIND_FILE_GATE = Project.KIND_FILE_GATE
SOURCE_KIND_FILE_CLEAN = Project.KIND_FILE_CLEAN
SOURCE_SLOT_SCHEMA = "schema"
SOURCE_SLOT_LABEL_SCHEMA = "Esquema"
SOURCE_SLOT_READ_PROFILE = "read_profile"
SOURCE_SLOT_LABEL_READ_PROFILE = "Perfil de lectura"

SOURCE_KIND_CHOICES_MATCH = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
)
SOURCE_KIND_CHOICES_SPLIT_MERGE = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Perfil de lectura"),
)
# Alias histórico P0 Match
SOURCE_KIND_CHOICES_P0 = SOURCE_KIND_CHOICES_MATCH

SUPPORTED_TARGET_KINDS = frozenset(
    {
        Project.KIND_FILE_MATCH,
        Project.KIND_FILE_SPLIT_MERGE,
    }
)


def parse_source_project_id(raw: str | None) -> UUID | None:
    """Parse Project primary key (UUID). Empty or invalid → None."""
    value = (raw or "").strip()
    if not value:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


def user_can_import(user, target_project: Project) -> bool:
    """PA/ED on supported destination kinds may open Importar estructura."""
    if target_project is None:
        return False
    if target_project.is_archived:
        return False
    if target_project.project_kind not in SUPPORTED_TARGET_KINDS:
        return False
    membership = project_service.get_membership(user, target_project)
    if membership is None:
        return False
    return membership.role in (
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
    )


def _target_slot_meta(target_project: Project) -> tuple[str, str, str, str]:
    """kind_label, slot, slot_label, effect_copy."""
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return (
            "FILE SPLIT/MERGE",
            TARGET_SLOT_READ_PROFILE,
            TARGET_SLOT_LABEL_READ_PROFILE,
            "Solo borrador del perfil de lectura — publicar Split/Merge es un módulo posterior",
        )
    return (
        "FILE MATCH",
        TARGET_SLOT_PROFILE_A,
        TARGET_SLOT_LABEL_PROFILE_A,
        "Solo borrador del Perfil A — la publicación Match sigue siendo el Módulo 4",
    )


def get_seed_host(target_project: Project) -> dict:
    """URL names / labels so shared templates/profile_seed work on any host app."""
    slug_kw = {"project_slug": target_project.slug}
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return {
            "app_label": "File Split/Merge",
            "app_list_url_name": "file_split_merge:project_list",
            "project_hub_url_name": "file_split_merge:project_hub",
            "profile_hub_url_name": "file_split_merge:profile_hub",
            "profile_hub_label": "Perfil",
            "scope_include": "file_split_merge/profile/_project_scope.html",
            "seed_hub_url_name": "file_split_merge:profile_seed_hub",
            "seed_hub_help_url_name": "file_split_merge:profile_seed_hub_help",
            "seed_picker_url_name": "file_split_merge:profile_seed_picker",
            "seed_picker_help_url_name": "file_split_merge:profile_seed_picker_help",
            "seed_apply_url_name": "file_split_merge:profile_seed_apply",
            "seed_apply_help_url_name": "file_split_merge:profile_seed_apply_help",
            "seed_history_url_name": "file_split_merge:profile_seed_history",
            "seed_history_help_url_name": "file_split_merge:profile_seed_history_help",
            "seed_history_detail_url_name": "file_split_merge:profile_seed_history_detail",
            "nav_active": "file_split_merge",
            "nav_open_flag": "file_split_merge_nav_open",
            **slug_kw,
        }
    return {
        "app_label": "FILE MATCH",
        "app_list_url_name": "file_match:project_list",
        "project_hub_url_name": "file_match:project_hub",
        "profile_hub_url_name": "file_match:profile_a_hub",
        "profile_hub_label": "Perfil A",
        "scope_include": "file_match/profile_a/_project_scope.html",
        "seed_hub_url_name": "file_match:profile_a_seed_hub",
        "seed_hub_help_url_name": "file_match:profile_a_seed_hub_help",
        "seed_picker_url_name": "file_match:profile_a_seed_picker",
        "seed_picker_help_url_name": "file_match:profile_a_seed_picker_help",
        "seed_apply_url_name": "file_match:profile_a_seed_apply",
        "seed_apply_help_url_name": "file_match:profile_a_seed_apply_help",
        "seed_history_url_name": "file_match:profile_a_seed_history",
        "seed_history_help_url_name": "file_match:profile_a_seed_history_help",
        "seed_history_detail_url_name": "file_match:profile_a_seed_history_detail",
        "nav_active": "file_match",
        "nav_open_flag": "file_match_nav_open",
        **slug_kw,
    }


def get_seed_context(user, target_project: Project) -> dict:
    """Shell context for import entry (any supported host)."""
    can_import = user_can_import(user, target_project)
    kind_label, slot, slot_label, effect = _target_slot_meta(target_project)
    return {
        "can_seed_import": can_import,
        "target_kind": target_project.project_kind,
        "target_kind_label": kind_label,
        "target_slot": slot,
        "target_slot_label": slot_label,
        "target_effect_copy": effect,
        "seed_step": 1,
        "seed_steps_total": 3,
        "seed_host": get_seed_host(target_project),
    }


def get_profile_a_seed_context(user, target_project: Project) -> dict:
    """Compat: Match Perfil A import entry (M1)."""
    return get_seed_context(user, target_project)


def get_split_merge_seed_context(user, target_project: Project) -> dict:
    return get_seed_context(user, target_project)


def _source_kind_choices_for(target_project: Project) -> tuple:
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return SOURCE_KIND_CHOICES_SPLIT_MERGE
    return SOURCE_KIND_CHOICES_MATCH


def _is_kind_supported(target_project: Project, source_kind: str) -> bool:
    return any(code == source_kind for code, _ in _source_kind_choices_for(target_project))


def _msg_no_sources(source_kind: str) -> str:
    if source_kind == SOURCE_KIND_FILE_CLEAN:
        return MSG_NO_SOURCES_CLEAN
    return MSG_NO_SOURCES_GATE


def _source_row_from_published(
    project: Project,
    *,
    kind: str,
    kind_label: str,
    slot: str,
    slot_label: str,
) -> dict | None:
    published = file_intake_persistence_service.get_published_version(project)
    if published is None:
        return None
    profile = getattr(published, "source_profile", None)
    if profile is None:
        return None
    source = source_persistence_service.profile_to_dict(profile)
    fields = source.get("fields") or []
    version_number = published.version_number
    return {
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "kind": kind,
        "kind_label": kind_label,
        "slot": slot,
        "slot_label": slot_label,
        "version_number": version_number,
        "version_label": f"v{version_number}",
        "file_type_code": source.get("file_type_code") or "—",
        "fields_count": len(fields),
        "published_at": published.published_at,
    }


def _source_row_from_gate(project: Project) -> dict | None:
    return _source_row_from_published(
        project,
        kind=SOURCE_KIND_FILE_GATE,
        kind_label="FILE GATE",
        slot=SOURCE_SLOT_SCHEMA,
        slot_label=SOURCE_SLOT_LABEL_SCHEMA,
    )


def _source_row_from_clean(project: Project) -> dict | None:
    return _source_row_from_published(
        project,
        kind=SOURCE_KIND_FILE_CLEAN,
        kind_label="FILE CLEAN",
        slot=SOURCE_SLOT_READ_PROFILE,
        slot_label=SOURCE_SLOT_LABEL_READ_PROFILE,
    )


def list_eligible_sources(
    user,
    target_project: Project,
    source_kind: str = SOURCE_KIND_FILE_GATE,
) -> list[dict]:
    """Published origins visible to user for seeding into target."""
    if target_project is None:
        return []
    if not _is_kind_supported(target_project, source_kind):
        return []

    company_id = target_project.company_id
    published_filter = {
        "is_archived": False,
        "company_id": company_id,
        "dms_config__current_version__status": DmsMappingVersion.STATUS_PUBLISHED,
    }
    select_related = (
        "dms_config",
        "dms_config__current_version",
        "dms_config__current_version__source_profile",
    )

    if source_kind == SOURCE_KIND_FILE_GATE:
        qs = (
            gate_project_service.visible_projects_qs(user)
            .filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_gate(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_FILE_CLEAN:
        qs = (
            clean_project_service.visible_projects_qs(user)
            .filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_clean(project)
            if row is not None:
                rows.append(row)
        return rows

    return []


def get_source_picker_context(
    user,
    target_project: Project,
    *,
    source_kind: str | None = None,
    source_id: UUID | None = None,
) -> dict:
    """Context for origin picker (Match A or Split/Merge)."""
    base = get_seed_context(user, target_project)
    choices = _source_kind_choices_for(target_project)
    default_kind = choices[0][0] if choices else SOURCE_KIND_FILE_GATE
    kind = (source_kind or default_kind).strip() or default_kind
    kind_supported = _is_kind_supported(target_project, kind)
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

    empty_cta = {
        "url_name": "file_gate:project_list",
        "label": "Ir a FILE GATE",
    }
    if kind == SOURCE_KIND_FILE_CLEAN:
        empty_cta = {
            "url_name": "file_clean:project_list",
            "label": "Ir a FILE CLEAN",
        }

    return {
        **base,
        "seed_step": 2,
        "source_kind": kind,
        "source_kind_choices": choices,
        "source_kind_supported": kind_supported,
        "sources": sources,
        "selected_source": selected,
        "selected_source_id": selected["id"] if selected else None,
        "invalid_source": invalid_source,
        "has_sources": bool(sources),
        "msg_no_sources": _msg_no_sources(kind),
        "msg_kind_unsupported": MSG_KIND_UNSUPPORTED,
        "empty_origins_cta": empty_cta,
        "picker_hint": (
            "FILE GATE (esquema) o FILE CLEAN (perfil) con versión publicada. "
            "Misma compañía · proyectos visibles para usted."
            if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE
            else "P0: FILE GATE con esquema publicado. Misma compañía · proyectos visibles para usted."
        ),
    }
