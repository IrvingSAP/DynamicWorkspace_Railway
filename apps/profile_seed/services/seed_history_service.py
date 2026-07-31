"""PROFILE_SEED M4 — historial de ProfileSeedEvent (seed_history.md)."""

from __future__ import annotations

from uuid import UUID

from django.urls import reverse

from apps.file_gate.projects.services import gate_project_service
from apps.profile_seed.models import ProfileSeedEvent
from apps.profile_seed.services import profile_seed_service
from apps.projects.models import Project

MSG_NO_EVENTS = "Aún no hay importaciones de estructura en este proyecto."
MSG_EVENT_NOT_FOUND = "Registro de importación no encontrado."
MSG_SOURCE_GONE = (
    "El proyecto origen ya no está disponible; se muestra el slug guardado."
)

STATUS_FILTER_CHOICES = (
    ("", "Todos"),
    (ProfileSeedEvent.STATUS_OK, "OK"),
    (ProfileSeedEvent.STATUS_FAILED, "Fallido"),
)

KIND_LABELS = {
    Project.KIND_FILE_GATE: "FILE GATE",
    Project.KIND_FILE_MATCH: "FILE MATCH",
    Project.KIND_REVERSE: "Reverse Studio",
    Project.KIND_DMS: "FilePipe / DMS",
}

SLOT_LABELS = {
    ProfileSeedEvent.SLOT_PROFILE_A: profile_seed_service.TARGET_SLOT_LABEL_PROFILE_A,
    ProfileSeedEvent.SLOT_SCHEMA: profile_seed_service.SOURCE_SLOT_LABEL_SCHEMA,
    "profile_b": "Perfil B (archivo B)",
    "input": "Entrada",
    "source": "Origen",
}


def _status_label(status: str) -> str:
    return dict(ProfileSeedEvent.STATUS_CHOICES).get(status, status)


def _created_by_label(user) -> str:
    if user is None:
        return "—"
    return getattr(user, "username", None) or str(user)


def _source_url(user, event: ProfileSeedEvent) -> str | None:
    source = event.source_project
    if source is None or source.is_archived:
        return None
    if source.project_kind != Project.KIND_FILE_GATE:
        return None
    if not gate_project_service.user_can_view(user, source):
        return None
    return reverse("file_gate:schema_hub", kwargs={"project_slug": source.slug})


def event_to_row(user, event: ProfileSeedEvent) -> dict:
    source_slug = event.source_slug or (
        event.source_project.slug if event.source_project_id else "—"
    )
    source_url = _source_url(user, event)
    return {
        "id": str(event.id),
        "created_at": event.created_at,
        "status": event.status,
        "status_label": _status_label(event.status),
        "message": event.message or "",
        "source_kind": event.source_kind,
        "source_kind_label": KIND_LABELS.get(event.source_kind, event.source_kind),
        "source_slug": source_slug,
        "source_version": event.source_version,
        "source_version_label": f"v{event.source_version}",
        "source_slot": event.source_slot,
        "source_slot_label": SLOT_LABELS.get(event.source_slot, event.source_slot),
        "source_project_id": event.source_project_id,
        "source_url": source_url,
        "source_available": source_url is not None,
        "target_slot": event.target_slot,
        "target_slot_label": SLOT_LABELS.get(
            event.target_slot, event.target_slot or "—"
        ),
        "mode": event.mode,
        "created_by_label": _created_by_label(event.created_by),
    }


def list_events(
    user,
    target_project: Project,
    *,
    status: str | None = None,
) -> list[dict]:
    qs = (
        ProfileSeedEvent.objects.filter(target_project=target_project)
        .select_related("source_project", "created_by")
        .order_by("-created_at")
    )
    status_value = (status or "").strip()
    if status_value in {
        ProfileSeedEvent.STATUS_OK,
        ProfileSeedEvent.STATUS_FAILED,
    }:
        qs = qs.filter(status=status_value)
    return [event_to_row(user, event) for event in qs]


def get_event(
    user, target_project: Project, event_id: str | UUID
) -> ProfileSeedEvent | None:
    try:
        event_uuid = event_id if isinstance(event_id, UUID) else UUID(str(event_id))
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        ProfileSeedEvent.objects.filter(
            id=event_uuid,
            target_project=target_project,
        )
        .select_related("source_project", "created_by", "target_project")
        .first()
    )


def get_history_hub_context(
    user,
    target_project: Project,
    *,
    status: str | None = None,
) -> dict:
    status_value = (status or "").strip()
    if status_value not in {
        "",
        ProfileSeedEvent.STATUS_OK,
        ProfileSeedEvent.STATUS_FAILED,
    }:
        status_value = ""
    events = list_events(user, target_project, status=status_value or None)
    return {
        **profile_seed_service.get_profile_a_seed_context(user, target_project),
        "events": events,
        "has_events": bool(events),
        "status_filter": status_value,
        "status_filter_choices": STATUS_FILTER_CHOICES,
        "msg_no_events": MSG_NO_EVENTS,
        "has_any_history": ProfileSeedEvent.objects.filter(
            target_project=target_project
        ).exists(),
    }


def get_history_detail_context(
    user, target_project: Project, event_id: str | UUID
) -> dict | None:
    event = get_event(user, target_project, event_id)
    if event is None:
        return None
    row = event_to_row(user, event)
    return {
        **profile_seed_service.get_profile_a_seed_context(user, target_project),
        "event": row,
        "source_gone_hint": None
        if row["source_available"] or not row["source_slug"] or row["source_slug"] == "—"
        else MSG_SOURCE_GONE,
    }
