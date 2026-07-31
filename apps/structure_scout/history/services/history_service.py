"""Historial unificado STRUCTURE SCOUT M7 (history.md)."""

from __future__ import annotations

from apps.projects.models import Project
from apps.structure_scout.apply.services import apply_target_service
from apps.structure_scout.draft.services import save_draft_service
from apps.structure_scout.models import ScoutApply, StructureDraft

MSG_NO_ACCESS = "No tiene acceso a este proyecto Explorador."
MSG_DRAFT_NOT_FOUND = "Versión de borrador no encontrada."
MSG_APPLY_NOT_FOUND = "Registro de aplicación no encontrado."

TIPO_ALL = "all"
TIPO_DRAFT = "draft"
TIPO_APPLY = "apply"
TIPO_CHOICES = (
    (TIPO_ALL, "Todos"),
    (TIPO_DRAFT, "Borradores"),
    (TIPO_APPLY, "Applies"),
)

STATUS_LABELS = dict(StructureDraft.STATUS_CHOICES)
CONFIDENCE_LABELS = dict(StructureDraft.CONFIDENCE_CHOICES)
KIND_LABELS = dict(ScoutApply.KIND_CHOICES)
APPLY_STATUS_LABELS = dict(ScoutApply.STATUS_CHOICES)


def has_history_events(project: Project) -> bool:
    if StructureDraft.objects.filter(project=project).exists():
        return True
    return ScoutApply.objects.filter(project=project).exists()


def _field_count(draft: StructureDraft) -> int:
    payload = draft.payload or {}
    fields = (payload.get("draft") or {}).get("fields")
    if not fields:
        fields = (payload.get("source") or {}).get("fields")
    return len(fields or [])


def _user_label(user) -> str:
    if user is None:
        return "—"
    return str(user)


def _draft_event(draft: StructureDraft) -> dict:
    return {
        "event_type": TIPO_DRAFT,
        "event_type_label": "Borrador",
        "created_at": draft.created_at,
        "user_label": _user_label(draft.created_by),
        "draft": draft,
        "apply": None,
        "version": draft.version,
        "is_current": draft.is_current,
        "status": draft.status,
        "status_label": STATUS_LABELS.get(draft.status, draft.status),
        "sample_filename": draft.sample_filename or "—",
        "fields_count": _field_count(draft),
        "summary": (
            f"v{draft.version} · {STATUS_LABELS.get(draft.status, draft.status)} · "
            f"{_field_count(draft)} campos"
        ),
    }


def _apply_event(apply: ScoutApply) -> dict:
    target = apply.target_project
    target_slug = target.slug if target is not None else "—"
    kind_label = KIND_LABELS.get(apply.target_kind, apply.target_kind)
    status_label = APPLY_STATUS_LABELS.get(apply.status, apply.status)
    return {
        "event_type": TIPO_APPLY,
        "event_type_label": "Apply",
        "created_at": apply.created_at,
        "user_label": _user_label(apply.created_by),
        "draft": None,
        "apply": apply,
        "target_slug": target_slug,
        "target_kind": apply.target_kind,
        "kind_label": kind_label,
        "status": apply.status,
        "status_label": status_label,
        "draft_version": apply.draft_version,
        "summary": (
            f"{target_slug} · {kind_label} · {status_label} · draft v{apply.draft_version}"
        ),
        "message_short": (apply.message or "")[:120],
    }


def build_timeline(
    project: Project, *, tipo: str = TIPO_ALL, limit: int = 100
) -> list[dict]:
    events: list[dict] = []
    if tipo in (TIPO_ALL, TIPO_DRAFT):
        for draft in StructureDraft.objects.filter(project=project).select_related(
            "created_by"
        ):
            events.append(_draft_event(draft))
    if tipo in (TIPO_ALL, TIPO_APPLY):
        for apply in ScoutApply.objects.filter(project=project).select_related(
            "created_by", "target_project", "draft"
        ):
            events.append(_apply_event(apply))

    # Fecha desc; empate: apply antes que draft; luego id estable.
    type_rank = {TIPO_APPLY: 0, TIPO_DRAFT: 1}

    def sort_key(ev: dict):
        obj = ev["apply"] if ev["event_type"] == TIPO_APPLY else ev["draft"]
        return (
            -ev["created_at"].timestamp(),
            type_rank.get(ev["event_type"], 9),
            str(obj.pk) if obj is not None else "",
        )

    events.sort(key=sort_key)
    return events[:limit]


def get_hub_context(user, project: Project, *, tipo: str = TIPO_ALL) -> dict:
    if tipo not in {TIPO_ALL, TIPO_DRAFT, TIPO_APPLY}:
        tipo = TIPO_ALL
    events = build_timeline(project, tipo=tipo)
    has_any = has_history_events(project)
    return {
        "tipo": tipo,
        "tipo_choices": TIPO_CHOICES,
        "events": events,
        "has_any_history": has_any,
        "is_empty": not events,
        "can_view_examples": save_draft_service.user_can_view_examples(user, project),
        "can_export": save_draft_service.user_can_export(user, project),
    }


def get_draft_detail(user, project: Project, draft_id) -> dict | None:
    try:
        draft = StructureDraft.objects.select_related("created_by", "sample").get(
            pk=draft_id, project=project
        )
    except (StructureDraft.DoesNotExist, ValueError, TypeError):
        return None

    payload = draft.payload or {}
    if not save_draft_service.user_can_view_examples(user, project):
        payload = save_draft_service.strip_payload_examples(payload)

    source = payload.get("source") or {}
    return {
        "draft": draft,
        "payload": payload,
        "source": source,
        "fields_count": _field_count(draft),
        "status_label": STATUS_LABELS.get(draft.status, draft.status),
        "confidence_label": CONFIDENCE_LABELS.get(
            draft.confidence, draft.confidence or "—"
        ),
        "user_label": _user_label(draft.created_by),
        "can_export": save_draft_service.user_can_export(user, project),
        "can_view_examples": save_draft_service.user_can_view_examples(user, project),
        "pattern_chips": _pattern_chips(source),
    }


def _pattern_chips(source: dict) -> list[str]:
    chips = []
    ft = (source.get("file_type_code") or "").strip()
    if ft:
        chips.append(ft)
    enc = (source.get("encoding_code") or "").strip()
    if enc:
        chips.append(enc)
    delim = source.get("delimiter")
    if delim is not None and str(delim) != "":
        chips.append(f"delim {delim}")
    if source.get("has_header"):
        row = source.get("header_row") or 1
        chips.append(f"header {row}")
    return chips


def get_apply_detail(user, project: Project, apply_id) -> dict | None:
    try:
        apply = ScoutApply.objects.select_related(
            "created_by", "target_project", "draft"
        ).get(pk=apply_id, project=project)
    except (ScoutApply.DoesNotExist, ValueError, TypeError):
        return None

    target = apply.target_project
    deep_link = None
    target_active = False
    target_slug = "—"
    target_name = ""
    if target is not None:
        target_slug = target.slug
        target_name = target.name
        if not target.is_archived:
            target_active = True
            deep_link = apply_target_service.target_deep_link(target)

    return {
        "apply": apply,
        "status_label": APPLY_STATUS_LABELS.get(apply.status, apply.status),
        "kind_label": KIND_LABELS.get(apply.target_kind, apply.target_kind),
        "user_label": _user_label(apply.created_by),
        "target_slug": target_slug,
        "target_name": target_name,
        "target_active": target_active,
        "deep_link": deep_link,
        "draft": apply.draft,
        "draft_status_label": (
            STATUS_LABELS.get(apply.draft.status, apply.draft.status)
            if apply.draft is not None
            else ""
        ),
    }
