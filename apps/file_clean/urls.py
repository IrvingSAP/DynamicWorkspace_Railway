from django.urls import include, path

from apps.file_clean import guide_views

app_name = "file_clean"

urlpatterns = [
    path("ayuda/", guide_views.file_clean_guide, name="file_clean_guide"),
    path("proyectos/", include("apps.file_clean.projects.urls")),
    path(
        "proyectos/<slug:project_slug>/perfil/",
        include("apps.file_clean.profile.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/reglas/",
        include("apps.file_clean.rules.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/publicar/",
        include("apps.file_clean.publish.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/ejecutar/",
        include("apps.file_clean.run.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/historial/",
        include("apps.file_clean.history.urls"),
    ),
]
