from django.urls import path

from apps.structure_scout.history import views

urlpatterns = [
    path("", views.history_hub, name="history_hub"),
    path("ayuda/", views.history_hub_help, name="history_hub_help"),
    path(
        "borrador/<uuid:draft_id>/",
        views.history_draft,
        name="history_draft",
    ),
    path(
        "borrador/<uuid:draft_id>/exportar/",
        views.history_draft_export,
        name="history_draft_export",
    ),
    path(
        "borrador/<uuid:draft_id>/eliminar/",
        views.history_draft_delete,
        name="history_draft_delete",
    ),
    path(
        "apply/<uuid:apply_id>/",
        views.history_apply,
        name="history_apply",
    ),
    path(
        "apply/<uuid:apply_id>/eliminar/",
        views.history_apply_delete,
        name="history_apply_delete",
    ),
]
