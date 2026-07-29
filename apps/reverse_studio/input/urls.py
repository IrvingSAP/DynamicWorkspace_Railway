from django.urls import path

from apps.reverse_studio.input import views

urlpatterns = [
    path("", views.hub, name="input_hub"),
    path("ayuda/", views.hub_help, name="input_hub_help"),
    path("guardar/", views.input_save, name="input_save"),
    path("paso/1/ayuda/", views.step1_help, name="input_step1_help"),
    path("paso/1/", views.step1_file_type, name="input_step1"),
    path("paso/2/ayuda/", views.step2_help, name="input_step2_help"),
    path("paso/2/", views.step2_capture_start, name="input_step2"),
    path("paso/3/ayuda/", views.step3_help, name="input_step3_help"),
    path("paso/3/", views.step3_capture_end, name="input_step3"),
    path("paso/4/ayuda/", views.step4_help, name="input_step4_help"),
    path("paso/4/", views.step4_fields, name="input_step4"),
    path("paso/5/ayuda/", views.step5_help, name="input_step5_help"),
    path("paso/5/", views.step5_content_rules, name="input_step5"),
    path("paso/6/ayuda/", views.step6_help, name="input_step6_help"),
    path("paso/6/", views.step6_report, name="input_step6"),
]
