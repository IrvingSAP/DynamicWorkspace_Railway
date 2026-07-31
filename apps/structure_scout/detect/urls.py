from django.urls import path

from apps.structure_scout.detect import views

urlpatterns = [
    path("", views.detect_hub, name="detect_hub"),
    path("ayuda/", views.detect_hub_help, name="detect_hub_help"),
]
