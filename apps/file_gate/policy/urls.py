from django.urls import path

from apps.file_gate.policy import views

urlpatterns = [
    path("", views.hub, name="policy_hub"),
    path("ayuda/", views.hub_help, name="policy_hub_help"),
    path("guardar/", views.policy_save, name="policy_save"),
    path("paso/1/ayuda/", views.step1_help, name="policy_step1_help"),
    path("paso/1/", views.step1_collection, name="policy_step1"),
    path("paso/2/ayuda/", views.step2_help, name="policy_step2_help"),
    path("paso/2/", views.step2_threshold, name="policy_step2"),
    path("paso/3/ayuda/", views.step3_help, name="policy_step3_help"),
    path("paso/3/", views.step3_review, name="policy_step3"),
]
