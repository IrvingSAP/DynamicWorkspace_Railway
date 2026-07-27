from django.urls import path

from apps.file_gate.bridge import views

urlpatterns = [
    path("", views.hub, name="bridge_hub"),
    path("ayuda/", views.hub_help, name="bridge_hub_help"),
]
