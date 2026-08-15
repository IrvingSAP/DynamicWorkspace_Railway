from django.urls import path

from apps.dms.target_profile import views

urlpatterns = [
    path("", views.hub, name="target_hub"),
    path("ayuda/", views.hub_help, name="target_hub_help"),
    path("importar/", views.target_seed_hub, name="target_seed_hub"),
    path("importar/ayuda/", views.target_seed_hub_help, name="target_seed_hub_help"),
    path("importar/origen/", views.target_seed_picker, name="target_seed_picker"),
    path(
        "importar/origen/ayuda/",
        views.target_seed_picker_help,
        name="target_seed_picker_help",
    ),
    path("importar/confirmar/", views.target_seed_apply, name="target_seed_apply"),
    path(
        "importar/confirmar/ayuda/",
        views.target_seed_apply_help,
        name="target_seed_apply_help",
    ),
    path("importar/historial/", views.target_seed_history, name="target_seed_history"),
    path(
        "importar/historial/ayuda/",
        views.target_seed_history_help,
        name="target_seed_history_help",
    ),
    path(
        "importar/historial/<uuid:event_id>/",
        views.target_seed_history_detail,
        name="target_seed_history_detail",
    ),
    path("guardar/", views.target_save, name="target_save"),
    path("paso/1/ayuda/", views.step1_help, name="target_step1_help"),
    path("paso/1/", views.step1_file_type, name="target_step1"),
    path("paso/2/ayuda/", views.step2_help, name="target_step2_help"),
    path("paso/2/", views.step2_encoding, name="target_step2"),
    path("paso/3/ayuda/", views.step3_help, name="target_step3_help"),
    path("paso/3/", views.step3_layout, name="target_step3"),
    path("paso/4/ayuda/", views.step4_help, name="target_step4_help"),
    path("paso/4/desde-origen/", views.import_fields_from_source, name="target_step4_import_source"),
    path("paso/4/", views.step4_fields, name="target_step4"),
    path("paso/5/ayuda/", views.step5_help, name="target_step5_help"),
    path("paso/5/", views.step5_serialization, name="target_step5"),
    path("paso/6/ayuda/", views.step6_help, name="target_step6_help"),
    path("paso/6/", views.step6_write_validation, name="target_step6"),
]
