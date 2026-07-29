from django.urls import path

from apps.reverse_studio.output import views

urlpatterns = [
    path("", views.hub, name="output_hub"),
    path("ayuda/", views.hub_help, name="output_hub_help"),
    path("guardar/", views.output_save, name="output_save"),
    path("paso/1/ayuda/", views.step1_help, name="output_step1_help"),
    path("paso/1/", views.step1_file_type, name="output_step1"),
    path("paso/2/ayuda/", views.step2_help, name="output_step2_help"),
    path("paso/2/", views.step2_encoding, name="output_step2"),
    path("paso/3/ayuda/", views.step3_help, name="output_step3_help"),
    path("paso/3/", views.step3_layout, name="output_step3"),
    path("paso/4/ayuda/", views.step4_help, name="output_step4_help"),
    path(
        "paso/4/desde-entrada/",
        views.import_fields_from_input,
        name="output_step4_import_input",
    ),
    path("paso/4/", views.step4_fields, name="output_step4"),
    path("paso/5/ayuda/", views.step5_help, name="output_step5_help"),
    path("paso/5/", views.step5_serialization, name="output_step5"),
    path("paso/6/ayuda/", views.step6_help, name="output_step6_help"),
    path("paso/6/", views.step6_write_validation, name="output_step6"),
]
