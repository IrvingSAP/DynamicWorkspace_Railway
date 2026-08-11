from django.urls import path

from apps.file_clean.rules import views

urlpatterns = [
    path("", views.rules_hub, name="rules_hub"),
    path("ayuda/", views.rules_hub_help, name="rules_hub_help"),
    path("nueva/", views.rules_add, name="rules_add"),
    path("<str:rule_id>/editar/", views.rules_edit, name="rules_edit"),
    path("<str:rule_id>/toggle/", views.rules_toggle, name="rules_toggle"),
    path("<str:rule_id>/eliminar/", views.rules_delete, name="rules_delete"),
    path("<str:rule_id>/mover/", views.rules_move, name="rules_move"),
]
