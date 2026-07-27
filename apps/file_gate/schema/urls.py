from django.urls import path

from apps.file_gate.schema import views

urlpatterns = [
    path("", views.hub, name="schema_hub"),
    path("ayuda/", views.hub_help, name="schema_hub_help"),
    path("guardar/", views.schema_save, name="schema_save"),
    path("publicar/", views.schema_publish, name="schema_publish"),
    path("paso/1/ayuda/", views.step1_help, name="schema_step1_help"),
    path("paso/1/", views.step1_file_type, name="schema_step1"),
    path("paso/2/ayuda/", views.step2_help, name="schema_step2_help"),
    path("paso/2/", views.step2_capture_start, name="schema_step2"),
    path("paso/3/ayuda/", views.step3_help, name="schema_step3_help"),
    path("paso/3/", views.step3_capture_end, name="schema_step3"),
    path("paso/4/ayuda/", views.step4_help, name="schema_step4_help"),
    path("paso/4/", views.step4_fields, name="schema_step4"),
    path("paso/4/delimitado/", views.step4_fields_delimited, name="schema_step4_delimited"),
    path("paso/5/ayuda/", views.step5_help, name="schema_step5_help"),
    path("paso/5/", views.step5_content_rules, name="schema_step5"),
    path("paso/6/ayuda/", views.step6_help, name="schema_step6_help"),
    path("paso/6/", views.step6_report, name="schema_step6"),
]
