from django.urls import path

from apps.reverse_studio.history import views

urlpatterns = [
    path("", views.hub, name="history_hub"),
    path("ayuda/", views.hub_help, name="history_hub_help"),
    path("jobs/<uuid:job_id>/", views.detail, name="history_detail"),
]
