from django.urls import path

from apps.dms.transform_execution import views

urlpatterns = [
    path("", views.hub, name="transform_execution_hub"),
    path("ayuda/", views.hub_help, name="transform_execution_hub_help"),
    path("historial/ayuda/", views.history_help, name="transform_execution_history_help"),
    path("historial/", views.history, name="transform_execution_history"),
    path(
        "jobs/<uuid:job_id>/preview/",
        views.job_preview,
        name="transform_execution_preview",
    ),
    path(
        "jobs/<uuid:job_id>/run/",
        views.job_run,
        name="transform_execution_run",
    ),
    path(
        "jobs/<uuid:job_id>/download/output/",
        views.download_output,
        name="transform_execution_download_output",
    ),
    path(
        "jobs/<uuid:job_id>/download/report/",
        views.download_report,
        name="transform_execution_download_report",
    ),
    path(
        "jobs/<uuid:job_id>/download/errors/",
        views.download_errors,
        name="transform_execution_download_errors",
    ),
]
