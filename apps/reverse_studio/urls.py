from django.urls import include, path

from apps.reverse_studio import guide_views

app_name = "reverse_studio"

urlpatterns = [
    path("ayuda/", guide_views.reverse_studio_guide, name="reverse_studio_guide"),
    path("proyectos/", include("apps.reverse_studio.projects.urls")),
    path(
        "proyectos/<slug:project_slug>/entrada/",
        include("apps.reverse_studio.input.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/salida/",
        include("apps.reverse_studio.output.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/mapeo/",
        include("apps.reverse_studio.mapping.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/publicar/",
        include("apps.reverse_studio.publish.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/generar/",
        include("apps.reverse_studio.run.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/historial/",
        include("apps.reverse_studio.history.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/bridge/",
        include("apps.reverse_studio.bridge.urls"),
    ),
]
