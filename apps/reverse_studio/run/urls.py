from django.urls import path

from apps.reverse_studio.run import views

urlpatterns = [
    path("", views.hub, name="run_hub"),
    path("ayuda/", views.hub_help, name="run_hub_help"),
    path("recientes/", views.recent, name="run_recent"),
    path("subir/", views.production_upload, name="run_production_upload"),
    path(
        "jobs/<uuid:job_id>/preview/",
        views.job_preview,
        name="run_preview",
    ),
    path(
        "jobs/<uuid:job_id>/generar/",
        views.job_generate,
        name="run_generate",
    ),
    path(
        "jobs/<uuid:job_id>/download/output/",
        views.download_output,
        name="run_download_output",
    ),
    path(
        "jobs/<uuid:job_id>/download/report/",
        views.download_report,
        name="run_download_report",
    ),
    path(
        "jobs/<uuid:job_id>/download/errors/",
        views.download_errors,
        name="run_download_errors",
    ),
]
