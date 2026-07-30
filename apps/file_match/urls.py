from django.urls import include, path

from apps.file_match import guide_views

app_name = "file_match"

urlpatterns = [
    path("ayuda/", guide_views.file_match_guide, name="file_match_guide"),
    path("proyectos/", include("apps.file_match.projects.urls")),
    path(
        "proyectos/<slug:project_slug>/perfil-a/",
        include("apps.file_match.profile_a.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/perfil-b/",
        include("apps.file_match.profile_b.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/reglas/",
        include("apps.file_match.rules.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/publicar/",
        include("apps.file_match.publish.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/ejecutar/",
        include("apps.file_match.run.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/informe/<uuid:job_id>/",
        include("apps.file_match.report.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/historial/",
        include("apps.file_match.history.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/bridge/",
        include("apps.file_match.bridge.urls"),
    ),
]
