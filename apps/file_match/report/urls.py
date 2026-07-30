from django.urls import path

from apps.file_match.report import views

urlpatterns = [
    path("", views.detail, name="report_detail"),
    path("ayuda/", views.detail_help, name="report_detail_help"),
    path("certificado/", views.certificate, name="report_certificate"),
    path(
        "certificado/descargar/",
        views.certificate_download,
        name="report_certificate_download",
    ),
]
