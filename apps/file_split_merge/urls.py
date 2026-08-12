from django.urls import include, path

from apps.file_split_merge import guide_views

app_name = "file_split_merge"

urlpatterns = [
    path("ayuda/", guide_views.file_split_merge_guide, name="file_split_merge_guide"),
    path("proyectos/", include("apps.file_split_merge.projects.urls")),
    path(
        "proyectos/<slug:project_slug>/perfil/",
        include("apps.file_split_merge.profile.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/reglas/",
        include("apps.file_split_merge.rules.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/publicar/",
        include("apps.file_split_merge.publish.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/ejecutar/",
        include("apps.file_split_merge.run.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/historial/",
        include("apps.file_split_merge.history.urls"),
    ),
]
