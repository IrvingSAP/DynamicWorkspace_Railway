from django.urls import path

from apps.file_clean.profile import views

urlpatterns = [
    path("", views.hub, name="profile_hub"),
    path("ayuda/", views.hub_help, name="profile_hub_help"),
    path("guardar/", views.profile_save, name="profile_save"),
    path("paso/1/ayuda/", views.step1_help, name="profile_step1_help"),
    path("paso/1/", views.step1_file_type, name="profile_step1"),
    path("paso/2/ayuda/", views.step2_help, name="profile_step2_help"),
    path("paso/2/", views.step2_capture_start, name="profile_step2"),
    path("paso/3/ayuda/", views.step3_help, name="profile_step3_help"),
    path("paso/3/", views.step3_capture_end, name="profile_step3"),
    path("paso/4/ayuda/", views.step4_help, name="profile_step4_help"),
    path("paso/4/", views.step4_fields, name="profile_step4"),
    path("paso/4/delimitado/", views.step4_fields_delimited, name="profile_step4_delimited"),
]
