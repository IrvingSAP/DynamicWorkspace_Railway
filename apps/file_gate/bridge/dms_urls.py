from django.urls import path

from apps.file_gate.bridge import dms_views

urlpatterns = [
    path("", dms_views.settings, name="file_gate_bridge_settings"),
    path("ayuda/", dms_views.settings_help, name="file_gate_bridge_settings_help"),
]
