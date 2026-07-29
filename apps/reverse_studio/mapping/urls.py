from django.urls import path

from apps.reverse_studio.mapping import views

urlpatterns = [
    path("", views.hub, name="mapping_hub"),
    path("ayuda/", views.hub_help, name="mapping_hub_help"),
    path("editor/ayuda/", views.editor_help, name="mapping_editor_help"),
    path("editor/", views.editor, name="mapping_editor"),
    path("guardar/", views.mapping_save, name="mapping_save"),
    path("preview/", views.mapping_preview, name="mapping_preview"),
    path("reglas/", views.rules_hub, name="mapping_rules_hub"),
    path("reglas/ayuda/", views.rules_hub_help, name="mapping_rules_hub_help"),
    path("reglas/editor/ayuda/", views.rules_editor_help, name="mapping_rules_editor_help"),
    path("reglas/editor/", views.rules_editor, name="mapping_rules_editor"),
    path("reglas/guardar/", views.rules_save, name="mapping_rules_save"),
    path("reglas/preview/", views.rules_preview, name="mapping_rules_preview"),
]
