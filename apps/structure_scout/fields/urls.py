from django.urls import path

from apps.structure_scout.fields import views

urlpatterns = [
    path("", views.fields_hub, name="fields_hub"),
    path("ayuda/", views.fields_hub_help, name="fields_hub_help"),
]
