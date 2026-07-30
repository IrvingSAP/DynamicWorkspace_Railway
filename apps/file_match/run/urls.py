from django.urls import path

from apps.file_match.run import views

urlpatterns = [
    path("", views.hub, name="run_hub"),
    path("ayuda/", views.hub_help, name="run_hub_help"),
    path("ejecutar/", views.run_execute, name="run_execute"),
    path("jobs/<uuid:job_id>/", views.run_result, name="run_result"),
    path("jobs/<uuid:job_id>/ayuda/", views.result_help, name="run_result_help"),
    path(
        "jobs/<uuid:job_id>/descargar/<str:kind>/",
        views.run_download,
        name="run_download",
    ),
]
