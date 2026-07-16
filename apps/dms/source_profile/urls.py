from django.urls import path

from apps.dms.source_profile import views

urlpatterns = [
    path("", views.hub, name="source_hub"),
    path("ayuda/", views.hub_help, name="source_hub_help"),
    path("guardar/", views.source_save, name="source_save"),
    path("publicar/", views.source_publish, name="source_publish"),
    path("paso/1/ayuda/", views.step1_help, name="source_step1_help"),
    path("paso/1/", views.step1_file_type, name="source_step1"),
    path("paso/2/ayuda/", views.step2_help, name="source_step2_help"),
    path("paso/2/", views.step2_capture_start, name="source_step2"),
    path("paso/3/ayuda/", views.step3_help, name="source_step3_help"),
    path("paso/3/", views.step3_capture_end, name="source_step3"),
    path("paso/4/ayuda/", views.step4_help, name="source_step4_help"),
    path("paso/4/", views.step4_fields, name="source_step4"),
    path("paso/4/delimitado/", views.step4_fields_delimited, name="source_step4_delimited"),
    path("paso/5/ayuda/", views.step5_help, name="source_step5_help"),
    path("paso/5/", views.step5_content_rules, name="source_step5"),
    path("paso/6/ayuda/", views.step6_help, name="source_step6_help"),
    path("paso/6/", views.step6_report, name="source_step6"),
]
