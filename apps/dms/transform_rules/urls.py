from django.urls import path

from apps.dms.transform_rules import views

urlpatterns = [
    path("", views.hub, name="transform_rules_hub"),
    path("ayuda/", views.hub_help, name="transform_rules_hub_help"),
    path("editor/ayuda/", views.editor_help, name="transform_rules_editor_help"),
    path("editor/", views.editor, name="transform_rules_editor"),
    path("guardar/", views.rules_save, name="transform_rules_save"),
    path("preview/", views.rules_preview, name="transform_rules_preview"),
]
