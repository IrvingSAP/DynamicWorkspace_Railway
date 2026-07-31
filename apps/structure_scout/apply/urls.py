from django.urls import path

from apps.structure_scout.apply import views

urlpatterns = [
    path("", views.apply_hub, name="apply_hub"),
    path("ayuda/", views.apply_hub_help, name="apply_hub_help"),
]
