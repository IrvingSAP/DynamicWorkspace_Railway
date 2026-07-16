from django.urls import path

from apps.dms.field_mapping import views

urlpatterns = [
    path("", views.hub, name="field_mapping_hub"),
    path("ayuda/", views.hub_help, name="field_mapping_hub_help"),
    path("editor/ayuda/", views.editor_help, name="field_mapping_editor_help"),
    path("editor/", views.editor, name="field_mapping_editor"),
    path("guardar/", views.mapping_save, name="field_mapping_save"),
    path("preview/", views.mapping_preview, name="field_mapping_preview"),
]
