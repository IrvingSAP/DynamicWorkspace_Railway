from django.urls import path

from apps.file_match.history import views

urlpatterns = [
    path("", views.hub, name="history_hub"),
    path("ayuda/", views.hub_help, name="history_hub_help"),
    path("eliminar-mias/", views.delete_own_jobs, name="history_delete_own"),
    path("<uuid:job_id>/eliminar/", views.delete_job, name="history_delete_job"),
]
