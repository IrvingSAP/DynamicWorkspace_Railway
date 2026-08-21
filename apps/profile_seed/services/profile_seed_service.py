"""PROFILE_SEED — permisos, hub y selector de origen (Match A, Split/Merge, FilePipe)."""

from __future__ import annotations

from uuid import UUID

from apps.dms.file_intake.services import file_intake_persistence_service
from apps.dms.source_profile.models import DmsMappingVersion
from apps.dms.source_profile.services import source_persistence_service
from apps.dms.mapping.services import mapping_project_service
from apps.file_clean.projects.services import clean_project_service
from apps.file_gate.projects.services import gate_project_service
from apps.file_match.projects.services import match_project_service
from apps.reverse_studio.projects.services import reverse_project_service
from apps.file_split_merge.projects.services import split_merge_project_service
from apps.structure_scout.projects.services import scout_project_service
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
MSG_NO_SOURCES_GATE_OTHER = (
    "No hay otros proyectos FILE GATE publicados visibles. "
    "Publique un esquema en otro proyecto FILE GATE o pida acceso."
)
MSG_NO_SOURCES_CLEAN = (
    "No hay orígenes FILE CLEAN publicados visibles. "
    "Publique un perfil en FILE CLEAN o pida acceso a un proyecto Clean."
)
MSG_NO_SOURCES_CLEAN_OTHER = (
    "No hay otros proyectos FILE CLEAN publicados visibles. "
    "Publique un perfil en otro proyecto FILE CLEAN o pida acceso."
)
MSG_NO_SOURCES_DMS = (
    "No hay orígenes FilePipe publicados visibles. "
    "Publique una definición de origen en FilePipe o pida acceso."
)
MSG_NO_SOURCES_DMS_OTHER = (
    "No hay otros proyectos FilePipe publicados visibles. "
    "Publique un origen en otro proyecto FilePipe o pida acceso."
)
MSG_NO_SOURCES_MATCH = (
    "No hay orígenes FILE MATCH (Perfil A) publicados visibles. "
    "Publique el Perfil A en FILE MATCH o pida acceso a un proyecto Match."
)
MSG_NO_SOURCES_MATCH_B = (
    "No hay orígenes FILE MATCH (Perfil B) publicados visibles. "
    "Publique el Perfil B en FILE MATCH o pida acceso a un proyecto Match."
)
MSG_NO_SOURCES_REVERSE = (
    "No hay orígenes Reverse Studio (entrada) publicados visibles. "
    "Publique el contrato de entrada en Reverse Studio o pida acceso."
)
MSG_NO_SOURCES_REVERSE_OTHER = (
    "No hay otros proyectos Reverse Studio publicados visibles. "
    "Publique el contrato de entrada en otro proyecto Reverse Studio o pida acceso."
)
MSG_NO_SOURCES_SPLIT_MERGE = (
    "No hay orígenes FILE SPLIT/MERGE publicados visibles. "
    "Publique un perfil de lectura en FILE SPLIT/MERGE o pida acceso."
)
MSG_NO_SOURCES_SCOUT = (
    "No hay borradores STRUCTURE SCOUT visibles. "
    "Guarde un borrador de estructura en Explorador o pida acceso al proyecto."
)
# Compatibilidad con callers Match existentes
MSG_NO_SOURCES = MSG_NO_SOURCES_GATE
MSG_NO_ACCESS_MATCH = "No tiene acceso a este proyecto FILE MATCH."

TARGET_SLOT_PROFILE_A = "profile_a"
TARGET_SLOT_LABEL_PROFILE_A = "Perfil A (archivo A)"
TARGET_SLOT_READ_PROFILE = "read_profile"
TARGET_SLOT_LABEL_READ_PROFILE = "Perfil de lectura"
TARGET_SLOT_SOURCE = "source"
TARGET_SLOT_LABEL_SOURCE = "Definición de origen"
TARGET_SLOT_TARGET = "target"
TARGET_SLOT_LABEL_TARGET = "Definición de destino"

SOURCE_KIND_FILE_GATE = Project.KIND_FILE_GATE
SOURCE_KIND_FILE_CLEAN = Project.KIND_FILE_CLEAN
SOURCE_KIND_DMS = Project.KIND_DMS
SOURCE_KIND_FILE_MATCH = Project.KIND_FILE_MATCH
SOURCE_KIND_FILE_MATCH_B = "file_match_b"
SOURCE_KIND_REVERSE = Project.KIND_REVERSE
SOURCE_KIND_SPLIT_MERGE = Project.KIND_FILE_SPLIT_MERGE
SOURCE_KIND_SCOUT = Project.KIND_STRUCTURE_SCOUT
SOURCE_SLOT_SCHEMA = "schema"
SOURCE_SLOT_LABEL_SCHEMA = "Esquema"
SOURCE_SLOT_READ_PROFILE = "read_profile"
SOURCE_SLOT_LABEL_READ_PROFILE = "Perfil de lectura"
SOURCE_SLOT_SOURCE = TARGET_SLOT_SOURCE
SOURCE_SLOT_LABEL_DMS_SOURCE = TARGET_SLOT_LABEL_SOURCE
SOURCE_SLOT_PROFILE_A = TARGET_SLOT_PROFILE_A
SOURCE_SLOT_LABEL_PROFILE_A = TARGET_SLOT_LABEL_PROFILE_A
SOURCE_SLOT_PROFILE_B = "profile_b"
SOURCE_SLOT_LABEL_PROFILE_B = "Perfil B (archivo B)"
SOURCE_SLOT_INPUT = "input"
SOURCE_SLOT_LABEL_INPUT = "Entrada"
SOURCE_SLOT_DRAFT = "draft"
SOURCE_SLOT_LABEL_DRAFT = "Borrador Scout"

SOURCE_KIND_CHOICES_MATCH = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Perfil de lectura"),
    (SOURCE_KIND_DMS, "FilePipe — Origen"),
    (SOURCE_KIND_FILE_MATCH, "FILE MATCH — Otro Perfil A"),
    (SOURCE_KIND_FILE_MATCH_B, "FILE MATCH — Perfil B"),
    (SOURCE_KIND_REVERSE, "Reverse Studio — Entrada"),
    (SOURCE_KIND_SPLIT_MERGE, "FILE SPLIT/MERGE — Perfil de lectura"),
    (SOURCE_KIND_SCOUT, "STRUCTURE SCOUT — Borrador"),
)
SOURCE_KIND_CHOICES_SPLIT_MERGE = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Perfil de lectura"),
)
SOURCE_KIND_CHOICES_DMS = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Perfil de lectura"),
    (SOURCE_KIND_DMS, "FilePipe — Origen"),
    (SOURCE_KIND_FILE_MATCH, "FILE MATCH — Perfil A"),
    (SOURCE_KIND_FILE_MATCH_B, "FILE MATCH — Perfil B"),
    (SOURCE_KIND_REVERSE, "Reverse Studio — Entrada"),
    (SOURCE_KIND_SPLIT_MERGE, "FILE SPLIT/MERGE — Perfil de lectura"),
    (SOURCE_KIND_SCOUT, "STRUCTURE SCOUT — Borrador"),
)
SOURCE_KIND_CHOICES_GATE = (
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Otro esquema"),
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Perfil de lectura"),
    (SOURCE_KIND_DMS, "FilePipe — Origen"),
    (SOURCE_KIND_FILE_MATCH, "FILE MATCH — Perfil A"),
    (SOURCE_KIND_FILE_MATCH_B, "FILE MATCH — Perfil B"),
    (SOURCE_KIND_REVERSE, "Reverse Studio — Entrada"),
    (SOURCE_KIND_SPLIT_MERGE, "FILE SPLIT/MERGE — Perfil de lectura"),
    (SOURCE_KIND_SCOUT, "STRUCTURE SCOUT — Borrador"),
)
SOURCE_KIND_CHOICES_CLEAN = (
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Otro perfil"),
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
    (SOURCE_KIND_DMS, "FilePipe — Origen"),
    (SOURCE_KIND_FILE_MATCH, "FILE MATCH — Perfil A"),
    (SOURCE_KIND_FILE_MATCH_B, "FILE MATCH — Perfil B"),
    (SOURCE_KIND_REVERSE, "Reverse Studio — Entrada"),
    (SOURCE_KIND_SPLIT_MERGE, "FILE SPLIT/MERGE — Perfil de lectura"),
    (SOURCE_KIND_SCOUT, "STRUCTURE SCOUT — Borrador"),
)
SOURCE_KIND_CHOICES_REVERSE = (
    (SOURCE_KIND_REVERSE, "Reverse Studio — Otra entrada"),
    (SOURCE_KIND_FILE_GATE, "FILE GATE — Esquema"),
    (SOURCE_KIND_FILE_CLEAN, "FILE CLEAN — Perfil de lectura"),
    (SOURCE_KIND_DMS, "FilePipe — Origen"),
    (SOURCE_KIND_FILE_MATCH, "FILE MATCH — Perfil A"),
    (SOURCE_KIND_FILE_MATCH_B, "FILE MATCH — Perfil B"),
    (SOURCE_KIND_SPLIT_MERGE, "FILE SPLIT/MERGE — Perfil de lectura"),
    (SOURCE_KIND_SCOUT, "STRUCTURE SCOUT — Borrador"),
)
# Alias histórico P0 Match
SOURCE_KIND_CHOICES_P0 = SOURCE_KIND_CHOICES_MATCH

SUPPORTED_TARGET_KINDS = frozenset(
    {
        Project.KIND_FILE_MATCH,
        Project.KIND_FILE_SPLIT_MERGE,
        Project.KIND_DMS,
        Project.KIND_FILE_GATE,
        Project.KIND_FILE_CLEAN,
        Project.KIND_REVERSE,
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


def _target_slot_meta(
    target_project: Project, destination_slot: str | None = None
) -> tuple[str, str, str, str]:
    """kind_label, slot, slot_label, effect_copy."""
    slot = (destination_slot or "").strip()
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return (
            "FILE SPLIT/MERGE",
            TARGET_SLOT_READ_PROFILE,
            TARGET_SLOT_LABEL_READ_PROFILE,
            "Solo borrador del perfil de lectura — publicar Split/Merge es un módulo posterior",
        )
    if target_project.project_kind == Project.KIND_FILE_CLEAN:
        return (
            "FILE CLEAN",
            TARGET_SLOT_READ_PROFILE,
            TARGET_SLOT_LABEL_READ_PROFILE,
            "Solo borrador del perfil de lectura — no clona reglas de limpieza; publicar File Clean es el módulo 4",
        )
    if target_project.project_kind == Project.KIND_FILE_GATE:
        return (
            "FILE GATE",
            SOURCE_SLOT_SCHEMA,
            SOURCE_SLOT_LABEL_SCHEMA,
            "Solo borrador del contrato de validación — publicar FILE GATE es un paso aparte",
        )
    if target_project.project_kind == Project.KIND_REVERSE:
        return (
            "Reverse Studio",
            SOURCE_SLOT_INPUT,
            SOURCE_SLOT_LABEL_INPUT,
            "Solo borrador del contrato de entrada — publicar la definición Reverse es el Módulo 4",
        )
    if target_project.project_kind == Project.KIND_DMS and slot == TARGET_SLOT_TARGET:
        return (
            "FilePipe (Data Mapping)",
            TARGET_SLOT_TARGET,
            TARGET_SLOT_LABEL_TARGET,
            "Solo borrador de la definición de destino — publicar FilePipe es un paso aparte",
        )
    if target_project.project_kind == Project.KIND_DMS:
        return (
            "FilePipe (Data Mapping)",
            TARGET_SLOT_SOURCE,
            TARGET_SLOT_LABEL_SOURCE,
            "Solo borrador de la definición de origen — publicar FilePipe es un paso aparte",
        )
    return (
        "FILE MATCH",
        TARGET_SLOT_PROFILE_A,
        TARGET_SLOT_LABEL_PROFILE_A,
        "Solo borrador del Perfil A — la publicación Match sigue siendo el Módulo 4",
    )


def get_seed_host(
    target_project: Project, *, destination_slot: str | None = None
) -> dict:
    """URL names / labels so shared templates/profile_seed work on any host app."""
    slug_kw = {"project_slug": target_project.slug}
    if target_project.project_kind == Project.KIND_FILE_GATE:
        return {
            "app_label": "FILE GATE",
            "app_list_url_name": "file_gate:project_list",
            "project_hub_url_name": "file_gate:project_hub",
            "profile_hub_url_name": "file_gate:schema_hub",
            "profile_hub_label": "Contrato",
            "scope_include": "file_gate/schema/_project_scope.html",
            "seed_hub_url_name": "file_gate:schema_seed_hub",
            "seed_hub_help_url_name": "file_gate:schema_seed_hub_help",
            "seed_picker_url_name": "file_gate:schema_seed_picker",
            "seed_picker_help_url_name": "file_gate:schema_seed_picker_help",
            "seed_apply_url_name": "file_gate:schema_seed_apply",
            "seed_apply_help_url_name": "file_gate:schema_seed_apply_help",
            "seed_history_url_name": "file_gate:schema_seed_history",
            "seed_history_help_url_name": "file_gate:schema_seed_history_help",
            "seed_history_detail_url_name": "file_gate:schema_seed_history_detail",
            "nav_active": "file_gate",
            "nav_open_flag": "file_gate_nav_open",
            **slug_kw,
        }
    if target_project.project_kind == Project.KIND_REVERSE:
        return {
            "app_label": "Reverse Studio",
            "app_list_url_name": "reverse_studio:project_list",
            "project_hub_url_name": "reverse_studio:project_hub",
            "profile_hub_url_name": "reverse_studio:input_hub",
            "profile_hub_label": "Entrada",
            "scope_include": "reverse_studio/input/_project_scope.html",
            "seed_hub_url_name": "reverse_studio:input_seed_hub",
            "seed_hub_help_url_name": "reverse_studio:input_seed_hub_help",
            "seed_picker_url_name": "reverse_studio:input_seed_picker",
            "seed_picker_help_url_name": "reverse_studio:input_seed_picker_help",
            "seed_apply_url_name": "reverse_studio:input_seed_apply",
            "seed_apply_help_url_name": "reverse_studio:input_seed_apply_help",
            "seed_history_url_name": "reverse_studio:input_seed_history",
            "seed_history_help_url_name": "reverse_studio:input_seed_history_help",
            "seed_history_detail_url_name": "reverse_studio:input_seed_history_detail",
            "nav_active": "reverse_studio",
            "nav_open_flag": "reverse_studio_nav_open",
            **slug_kw,
        }
    if target_project.project_kind == Project.KIND_FILE_CLEAN:
        return {
            "app_label": "FILE CLEAN",
            "app_list_url_name": "file_clean:project_list",
            "project_hub_url_name": "file_clean:project_hub",
            "profile_hub_url_name": "file_clean:profile_hub",
            "profile_hub_label": "Perfil",
            "scope_include": "file_clean/profile/_project_scope.html",
            "seed_hub_url_name": "file_clean:profile_seed_hub",
            "seed_hub_help_url_name": "file_clean:profile_seed_hub_help",
            "seed_picker_url_name": "file_clean:profile_seed_picker",
            "seed_picker_help_url_name": "file_clean:profile_seed_picker_help",
            "seed_apply_url_name": "file_clean:profile_seed_apply",
            "seed_apply_help_url_name": "file_clean:profile_seed_apply_help",
            "seed_history_url_name": "file_clean:profile_seed_history",
            "seed_history_help_url_name": "file_clean:profile_seed_history_help",
            "seed_history_detail_url_name": "file_clean:profile_seed_history_detail",
            "nav_active": "file_clean",
            "nav_open_flag": "file_clean_nav_open",
            **slug_kw,
        }
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
    if target_project.project_kind == Project.KIND_DMS:
        if (destination_slot or "").strip() == TARGET_SLOT_TARGET:
            return {
                "app_label": "FilePipe",
                "app_list_url_name": "dms:mapping_list",
                "project_hub_url_name": "dms:mapping_hub",
                "profile_hub_url_name": "dms:target_hub",
                "profile_hub_label": "Destino",
                "scope_include": "dms/target_profile/_project_scope.html",
                "seed_hub_url_name": "dms:target_seed_hub",
                "seed_hub_help_url_name": "dms:target_seed_hub_help",
                "seed_picker_url_name": "dms:target_seed_picker",
                "seed_picker_help_url_name": "dms:target_seed_picker_help",
                "seed_apply_url_name": "dms:target_seed_apply",
                "seed_apply_help_url_name": "dms:target_seed_apply_help",
                "seed_history_url_name": "dms:target_seed_history",
                "seed_history_help_url_name": "dms:target_seed_history_help",
                "seed_history_detail_url_name": "dms:target_seed_history_detail",
                "nav_active": "filepipe_mapping",
                "nav_open_flag": "filepipe_nav_open",
                **slug_kw,
            }
        return {
            "app_label": "FilePipe",
            "app_list_url_name": "dms:mapping_list",
            "project_hub_url_name": "dms:mapping_hub",
            "profile_hub_url_name": "dms:source_hub",
            "profile_hub_label": "Origen",
            "scope_include": "dms/source_profile/_project_scope.html",
            "seed_hub_url_name": "dms:source_seed_hub",
            "seed_hub_help_url_name": "dms:source_seed_hub_help",
            "seed_picker_url_name": "dms:source_seed_picker",
            "seed_picker_help_url_name": "dms:source_seed_picker_help",
            "seed_apply_url_name": "dms:source_seed_apply",
            "seed_apply_help_url_name": "dms:source_seed_apply_help",
            "seed_history_url_name": "dms:source_seed_history",
            "seed_history_help_url_name": "dms:source_seed_history_help",
            "seed_history_detail_url_name": "dms:source_seed_history_detail",
            "nav_active": "filepipe_mapping",
            "nav_open_flag": "filepipe_nav_open",
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


def get_seed_context(
    user, target_project: Project, *, destination_slot: str | None = None
) -> dict:
    """Shell context for import entry (any supported host)."""
    can_import = user_can_import(user, target_project)
    kind_label, slot, slot_label, effect = _target_slot_meta(
        target_project, destination_slot
    )
    return {
        "can_seed_import": can_import,
        "target_kind": target_project.project_kind,
        "target_kind_label": kind_label,
        "target_slot": slot,
        "target_slot_label": slot_label,
        "target_effect_copy": effect,
        "seed_step": 1,
        "seed_steps_total": 3,
        "seed_host": get_seed_host(
            target_project, destination_slot=destination_slot
        ),
        "destination_slot": slot,
    }


def get_profile_a_seed_context(user, target_project: Project) -> dict:
    """Compat: Match Perfil A import entry (M1)."""
    return get_seed_context(user, target_project)


def get_split_merge_seed_context(user, target_project: Project) -> dict:
    return get_seed_context(user, target_project)


def _source_kind_choices_for(target_project: Project) -> tuple:
    if target_project.project_kind == Project.KIND_DMS:
        return SOURCE_KIND_CHOICES_DMS
    if target_project.project_kind == Project.KIND_FILE_GATE:
        return SOURCE_KIND_CHOICES_GATE
    if target_project.project_kind == Project.KIND_REVERSE:
        return SOURCE_KIND_CHOICES_REVERSE
    if target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        return SOURCE_KIND_CHOICES_SPLIT_MERGE
    if target_project.project_kind == Project.KIND_FILE_CLEAN:
        return SOURCE_KIND_CHOICES_CLEAN
    return SOURCE_KIND_CHOICES_MATCH


def _is_kind_supported(target_project: Project, source_kind: str) -> bool:
    return any(code == source_kind for code, _ in _source_kind_choices_for(target_project))


def _msg_no_sources(source_kind: str) -> str:
    if source_kind == SOURCE_KIND_FILE_CLEAN:
        return MSG_NO_SOURCES_CLEAN
    if source_kind == SOURCE_KIND_DMS:
        return MSG_NO_SOURCES_DMS
    if source_kind == SOURCE_KIND_FILE_MATCH:
        return MSG_NO_SOURCES_MATCH
    if source_kind == SOURCE_KIND_FILE_MATCH_B:
        return MSG_NO_SOURCES_MATCH_B
    if source_kind == SOURCE_KIND_REVERSE:
        return MSG_NO_SOURCES_REVERSE
    if source_kind == SOURCE_KIND_SPLIT_MERGE:
        return MSG_NO_SOURCES_SPLIT_MERGE
    if source_kind == SOURCE_KIND_SCOUT:
        return MSG_NO_SOURCES_SCOUT
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


def _source_row_from_dms(project: Project) -> dict | None:
    return _source_row_from_published(
        project,
        kind=SOURCE_KIND_DMS,
        kind_label="FilePipe",
        slot=SOURCE_SLOT_SOURCE,
        slot_label=SOURCE_SLOT_LABEL_DMS_SOURCE,
    )


def _source_row_from_match_a(project: Project) -> dict | None:
    return _source_row_from_published(
        project,
        kind=SOURCE_KIND_FILE_MATCH,
        kind_label="FILE MATCH",
        slot=SOURCE_SLOT_PROFILE_A,
        slot_label=SOURCE_SLOT_LABEL_PROFILE_A,
    )


def _source_row_from_match_b(project: Project) -> dict | None:
    from apps.file_match.models import FileMatchSourceB
    from apps.file_match.profile_b.services import profile_b_persistence_service

    published = file_intake_persistence_service.get_published_version(project)
    if published is None:
        return None
    try:
        profile = published.match_source_b
    except FileMatchSourceB.DoesNotExist:
        return None
    source = profile_b_persistence_service.profile_to_dict(profile)
    fields = source.get("fields") or []
    version_number = published.version_number
    return {
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "kind": SOURCE_KIND_FILE_MATCH_B,
        "kind_label": "FILE MATCH",
        "slot": SOURCE_SLOT_PROFILE_B,
        "slot_label": SOURCE_SLOT_LABEL_PROFILE_B,
        "version_number": version_number,
        "version_label": f"v{version_number}",
        "file_type_code": source.get("file_type_code") or "—",
        "fields_count": len(fields),
        "published_at": published.published_at,
    }


def _source_row_from_reverse(project: Project) -> dict | None:
    return _source_row_from_published(
        project,
        kind=SOURCE_KIND_REVERSE,
        kind_label="Reverse Studio",
        slot=SOURCE_SLOT_INPUT,
        slot_label=SOURCE_SLOT_LABEL_INPUT,
    )


def _source_row_from_split_merge(project: Project) -> dict | None:
    return _source_row_from_published(
        project,
        kind=SOURCE_KIND_SPLIT_MERGE,
        kind_label="FILE SPLIT/MERGE",
        slot=SOURCE_SLOT_READ_PROFILE,
        slot_label=SOURCE_SLOT_LABEL_READ_PROFILE,
    )


def _source_row_from_scout(project: Project) -> dict | None:
    from apps.structure_scout.draft.services import save_draft_service

    draft = save_draft_service.get_current_draft(project)
    if draft is None:
        return None
    source = (draft.payload or {}).get("source") or {}
    if not (source.get("file_type_code") or "").strip():
        return None
    fields = source.get("fields") or []
    return {
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "kind": SOURCE_KIND_SCOUT,
        "kind_label": "STRUCTURE SCOUT",
        "slot": SOURCE_SLOT_DRAFT,
        "slot_label": SOURCE_SLOT_LABEL_DRAFT,
        "version_number": draft.version,
        "version_label": f"v{draft.version}",
        "file_type_code": source.get("file_type_code") or "—",
        "fields_count": len(fields),
        "published_at": draft.created_at,
    }


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
        "dms_config__current_version__match_source_b",
    )

    if source_kind == SOURCE_KIND_FILE_GATE:
        qs = gate_project_service.visible_projects_qs(user)
        if target_project.project_kind == Project.KIND_FILE_GATE:
            qs = qs.exclude(pk=target_project.pk)
        qs = (
            qs.filter(**published_filter)
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
        qs = clean_project_service.visible_projects_qs(user)
        if target_project.project_kind == Project.KIND_FILE_CLEAN:
            qs = qs.exclude(pk=target_project.pk)
        qs = (
            qs.filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_clean(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_DMS:
        qs = (
            mapping_project_service.visible_projects_qs(user)
            .exclude(pk=target_project.pk)
            .filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_dms(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_FILE_MATCH:
        qs = (
            match_project_service.visible_projects_qs(user)
            .exclude(pk=target_project.pk)
            .filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_match_a(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_FILE_MATCH_B:
        qs = match_project_service.visible_projects_qs(user)
        if target_project.project_kind != Project.KIND_FILE_MATCH:
            qs = qs.exclude(pk=target_project.pk)
        qs = (
            qs.filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_match_b(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_REVERSE:
        qs = (
            reverse_project_service.visible_projects_qs(user)
            .exclude(pk=target_project.pk)
            .filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_reverse(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_SPLIT_MERGE:
        qs = (
            split_merge_project_service.visible_projects_qs(user)
            .exclude(pk=target_project.pk)
            .filter(**published_filter)
            .select_related(*select_related)
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_split_merge(project)
            if row is not None:
                rows.append(row)
        return rows

    if source_kind == SOURCE_KIND_SCOUT:
        qs = (
            scout_project_service.visible_projects_qs(user)
            .filter(
                is_archived=False,
                company_id=company_id,
                structure_drafts__is_current=True,
            )
            .distinct()
            .order_by("slug")
        )
        rows = []
        for project in qs:
            row = _source_row_from_scout(project)
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
    destination_slot: str | None = None,
) -> dict:
    """Context for origin picker (Match A, Split/Merge or FilePipe)."""
    base = get_seed_context(
        user, target_project, destination_slot=destination_slot
    )
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
    elif kind == SOURCE_KIND_DMS:
        empty_cta = {
            "url_name": "dms:mapping_list",
            "label": "Ir a FilePipe",
        }
    elif kind == SOURCE_KIND_FILE_MATCH:
        empty_cta = {
            "url_name": "file_match:project_list",
            "label": "Ir a FILE MATCH",
        }
    elif kind == SOURCE_KIND_FILE_MATCH_B:
        empty_cta = {
            "url_name": "file_match:project_list",
            "label": "Ir a FILE MATCH",
        }
    elif kind == SOURCE_KIND_REVERSE:
        empty_cta = {
            "url_name": "reverse_studio:project_list",
            "label": "Ir a Reverse Studio",
        }
    elif kind == SOURCE_KIND_SPLIT_MERGE:
        empty_cta = {
            "url_name": "file_split_merge:project_list",
            "label": "Ir a FILE SPLIT/MERGE",
        }
    elif kind == SOURCE_KIND_SCOUT:
        empty_cta = {
            "url_name": "structure_scout:project_list",
            "label": "Ir a STRUCTURE SCOUT",
        }

    if target_project.project_kind == Project.KIND_DMS:
        picker_hint = (
            "FILE GATE, FILE CLEAN, FilePipe (otro proyecto), FILE MATCH (A o B), "
            "Reverse Studio (entrada), FILE SPLIT/MERGE (perfil de lectura) "
            "o STRUCTURE SCOUT (borrador actual, no contrato publicado). "
            "Misma compañía · visibles para usted. "
            "No se lista este mismo proyecto FilePipe."
        )
    elif target_project.project_kind == Project.KIND_FILE_GATE:
        picker_hint = (
            "Otro FILE GATE (no este proyecto), FILE CLEAN (perfil de lectura publicado; "
            "no clona reglas de limpieza), FilePipe (origen publicado; no clona destino ni mapeo), "
            "FILE MATCH Perfil A o Perfil B (no clona reglas de cruce; A y B son slots distintos), "
            "Reverse Studio (entrada publicada; no clona salida ni reglas de generación), "
            "FILE SPLIT/MERGE (perfil de lectura publicado; no clona reglas de partición/fusión) "
            "o STRUCTURE SCOUT (borrador actual; no es contrato publicado; distinto de Aplicar a destino en Explorador). "
            "Misma compañía · visibles para usted. "
            "No se lista este mismo proyecto FILE GATE. No clona políticas de gate."
        )
    elif target_project.project_kind == Project.KIND_FILE_CLEAN:
        picker_hint = (
            "Otro FILE CLEAN (no este proyecto; no clona reglas de limpieza), FILE GATE (esquema publicado; "
            "no clona políticas), FilePipe (origen publicado; no destino ni mapeo), "
            "FILE MATCH Perfil A o B (no reglas de cruce), Reverse Studio (entrada publicada), "
            "FILE SPLIT/MERGE (perfil de lectura) o STRUCTURE SCOUT (borrador actual). "
            "Misma compañía · visibles para usted. "
            "No se lista este mismo proyecto FILE CLEAN."
        )
    elif target_project.project_kind == Project.KIND_REVERSE:
        picker_hint = (
            "Otra entrada Reverse Studio (no este proyecto), FILE GATE (esquema publicado; no clona políticas), "
            "FILE CLEAN (perfil de lectura; no clona reglas), FilePipe (origen publicado; no destino ni mapeo), "
            "FILE MATCH Perfil A o B (no reglas de cruce), FILE SPLIT/MERGE (perfil de lectura) "
            "o STRUCTURE SCOUT (borrador actual). "
            "Misma compañía · visibles para usted. "
            "No se lista este mismo proyecto Reverse. No clona layout de salida ni mapeo."
        )
    elif target_project.project_kind == Project.KIND_FILE_SPLIT_MERGE:
        picker_hint = (
            "FILE GATE (esquema) o FILE CLEAN (perfil) con versión publicada. "
            "Misma compañía · proyectos visibles para usted."
        )
    else:
        picker_hint = (
            "FILE GATE (esquema publicado; no clona políticas), FILE CLEAN (perfil; no clona reglas), "
            "FilePipe (origen; no destino ni mapeo), otro FILE MATCH Perfil A (no este proyecto), "
            "FILE MATCH Perfil B (incluye este proyecto si B está publicado; no clona reglas de cruce), "
            "Reverse Studio (entrada), FILE SPLIT/MERGE (perfil de lectura) "
            "o STRUCTURE SCOUT (borrador actual). "
            "Misma compañía · visibles para usted. No se lista este mismo Perfil A."
        )

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
        "msg_no_sources": (
            MSG_NO_SOURCES_GATE_OTHER
            if kind == SOURCE_KIND_FILE_GATE
            and target_project.project_kind == Project.KIND_FILE_GATE
            else MSG_NO_SOURCES_CLEAN_OTHER
            if kind == SOURCE_KIND_FILE_CLEAN
            and target_project.project_kind == Project.KIND_FILE_CLEAN
            else MSG_NO_SOURCES_REVERSE_OTHER
            if kind == SOURCE_KIND_REVERSE
            and target_project.project_kind == Project.KIND_REVERSE
            else MSG_NO_SOURCES_DMS_OTHER
            if kind == SOURCE_KIND_DMS
            and target_project.project_kind == Project.KIND_DMS
            else _msg_no_sources(kind)
        ),
        "msg_kind_unsupported": MSG_KIND_UNSUPPORTED,
        "empty_origins_cta": empty_cta,
        "picker_hint": picker_hint,
    }
