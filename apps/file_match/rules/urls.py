from django.urls import path

from apps.file_match.rules import views

urlpatterns = [
    path("", views.hub, name="rules_hub"),
    path("ayuda/", views.hub_help, name="rules_hub_help"),
    path("proponer-1a1/", views.suggest_homonyms, name="rules_suggest_homonyms"),
    path("guardar/", views.rules_save, name="rules_save"),
    path("claves/ayuda/", views.keys_help, name="rules_keys_help"),
    path("claves/", views.keys_edit, name="rules_keys"),
    path("comparar/ayuda/", views.compare_help, name="rules_compare_help"),
    path("comparar/", views.compare_edit, name="rules_compare"),
    path("normalizacion/ayuda/", views.normalize_help, name="rules_normalize_help"),
    path("normalizacion/", views.normalize_edit, name="rules_normalize"),
]
