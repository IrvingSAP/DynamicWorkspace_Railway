from django.urls import include, path

from apps.dms import guide_views

app_name = "dms"

urlpatterns = [
    path("ayuda/", guide_views.datamapping_guide, name="datamapping_guide"),
    path("mapping/", include("apps.dms.mapping.urls")),
    path("catalogs/", include("apps.dms.catalogs.urls")),
    path(
        "proyectos/<slug:project_slug>/origen/",
        include("apps.dms.source_profile.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/destino/",
        include("apps.dms.target_profile.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/mapeo/",
        include("apps.dms.field_mapping.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/reglas/",
        include("apps.dms.transform_rules.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/archivo/",
        include("apps.dms.file_intake.urls"),
    ),
    path(
        "proyectos/<slug:project_slug>/ejecutar/",
        include("apps.dms.transform_execution.urls"),
    ),
]
