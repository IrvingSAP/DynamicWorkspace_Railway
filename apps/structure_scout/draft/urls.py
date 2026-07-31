from django.urls import path

from apps.structure_scout.draft import views

urlpatterns = [
    path("", views.draft_hub, name="draft_hub"),
    path("ayuda/", views.draft_hub_help, name="draft_hub_help"),
    path("exportar/", views.draft_export, name="draft_export"),
]
