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
        "apply/<uuid:apply_id>/",
        views.history_apply,
        name="history_apply",
    ),
]
