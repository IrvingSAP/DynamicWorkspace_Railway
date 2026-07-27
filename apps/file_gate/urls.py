from django.urls import include, path

from apps.file_gate import guide_views

app_name = "file_gate"

urlpatterns = [
    path("ayuda/", guide_views.file_gate_guide, name="file_gate_guide"),
    path("proyectos/", include("apps.file_gate.projects.urls")),
    path(
        "proyectos/<slug:project_slug>/esquema/",
        include("apps.file_gate.schema.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/politicas/",
        include("apps.file_gate.policy.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/validar/",
        include("apps.file_gate.run.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/historial/",
        include("apps.file_gate.history.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/bridge/",
        include("apps.file_gate.bridge.urls"),
    ),
]
