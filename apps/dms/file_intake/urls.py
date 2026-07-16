from django.urls import path

from apps.dms.file_intake import views

urlpatterns = [
    path("", views.hub, name="file_intake_hub"),
    path("ayuda/", views.hub_help, name="file_intake_hub_help"),
    path("muestras/subir/", views.sample_upload, name="file_intake_sample_upload"),
    path(
        "muestras/<uuid:sample_id>/preview/",
        views.sample_preview,
        name="file_intake_sample_preview",
    ),
    path(
        "muestras/<uuid:sample_id>/eliminar/",
        views.sample_delete,
        name="file_intake_sample_delete",
    ),
    path(
        "ejecutar/subir/",
        views.production_upload,
        name="file_intake_production_upload",
    ),
]
