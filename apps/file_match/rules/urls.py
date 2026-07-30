from django.urls import path

from apps.file_match.rules import views

urlpatterns = [
    path("", views.hub, name="rules_hub"),
    path("ayuda/", views.hub_help, name="rules_hub_help"),
    path("guardar/", views.rules_save, name="rules_save"),
    path("claves/", views.keys_edit, name="rules_keys"),
    path("comparar/", views.compare_edit, name="rules_compare"),
    path("normalizacion/", views.normalize_edit, name="rules_normalize"),
]
