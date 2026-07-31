from django.urls import include, path

from apps.structure_scout import guide_views

app_name = "structure_scout"

urlpatterns = [
    path("ayuda/", guide_views.structure_scout_guide, name="structure_scout_guide"),
    path("proyectos/", include("apps.structure_scout.projects.urls")),
    path(
        "proyectos/<slug:project_slug>/muestra/",
        include("apps.structure_scout.sample.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/detectar/",
        include("apps.structure_scout.detect.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/campos/",
        include("apps.structure_scout.fields.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/borrador/",
        include("apps.structure_scout.draft.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/aplicar/",
        include("apps.structure_scout.apply.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/historial/",
        include("apps.structure_scout.history.urls"),
    ),
]
