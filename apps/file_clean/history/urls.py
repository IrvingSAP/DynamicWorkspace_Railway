from django.urls import path

from apps.file_clean.history import views

urlpatterns = [
    path("", views.hub, name="history_hub"),
    path("ayuda/", views.hub_help, name="history_hub_help"),
    path("eliminar-mias/", views.delete_own_jobs, name="history_delete_own"),
    path("<uuid:job_id>/", views.detail, name="history_detail"),
    path("<uuid:job_id>/ayuda/", views.detail_help, name="history_detail_help"),
    path("<uuid:job_id>/eliminar/", views.delete_job, name="history_delete_job"),
]
