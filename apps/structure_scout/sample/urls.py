from django.urls import path

from apps.structure_scout.sample import views

urlpatterns = [
    path("", views.sample_hub, name="sample_hub"),
    path("ayuda/", views.sample_hub_help, name="sample_hub_help"),
    # Paths named like DMS so static/js/file_intake.js can derive preview/delete URLs.
    path("muestras/subir/", views.sample_upload, name="sample_upload"),
    path(
        "muestras/<uuid:sample_id>/preview/",
        views.sample_preview,
        name="sample_preview",
    ),
    path(
        "muestras/<uuid:sample_id>/eliminar/",
        views.sample_delete,
        name="sample_delete",
    ),
]
