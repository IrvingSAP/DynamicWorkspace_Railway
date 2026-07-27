from django.urls import path

from apps.file_gate.history import views

urlpatterns = [
    path("", views.hub, name="history_hub"),
    path("ayuda/", views.hub_help, name="history_hub_help"),
]
