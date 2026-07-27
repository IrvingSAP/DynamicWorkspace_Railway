from django.urls import path

from apps.file_gate.report import views as report_views
from apps.file_gate.run import views

urlpatterns = [
    path("", views.hub, name="run_hub"),
    path("ayuda/", views.hub_help, name="run_hub_help"),
    path("subir/", views.upload, name="run_upload"),
    path("ejecutar/", views.run_execute, name="run_execute"),
    path("jobs/<uuid:job_id>/", views.run_result, name="run_result"),
    path("jobs/<uuid:job_id>/ayuda/", views.result_help, name="run_result_help"),
    path("jobs/<uuid:job_id>/descargar/<str:kind>/", views.run_download, name="run_download"),
    path("jobs/<uuid:job_id>/informe/", report_views.detail, name="report_detail"),
    path(
        "jobs/<uuid:job_id>/informe/ayuda/",
        report_views.detail_help,
        name="report_detail_help",
    ),
    path(
        "jobs/<uuid:job_id>/certificado/",
        report_views.certificate,
        name="report_certificate",
    ),
    path(
        "jobs/<uuid:job_id>/certificado/descargar/",
        report_views.certificate_download,
        name="report_certificate_download",
    ),
]
