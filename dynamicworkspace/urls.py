from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.platform_api.urls import api_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.public.urls")),
    path("", include("apps.security.urls")),
    path("app/", include("apps.dashboard.urls")),
    path("app/admin/compañias/", include("apps.company.urls")),
    path("app/admin/usuarios/", include("apps.accounts.urls")),
    path("app/admin/billing/", include("apps.billing.urls")),
    path(
        "app/proyectos/<slug:slug>/campos/",
        include(("apps.fields.urls", "fields")),
    ),
    path(
        "app/proyectos/<slug:slug>/registros/",
        include(("apps.records.urls", "records")),
    ),
    path("app/proyectos/", include("apps.projects.urls")),
    path("app/filepipe/", include("apps.dms.urls")),
    path("app/file-gate/", include("apps.file_gate.urls")),
    path("app/reverse-studio/", include("apps.reverse_studio.urls")),
    path("app/file-match/", include("apps.file_match.urls")),
    path("app/structure-scout/", include("apps.structure_scout.urls")),
    path("app/file-clean/", include("apps.file_clean.urls")),
    path("app/file-split-merge/", include("apps.file_split_merge.urls")),
    path("app/file-pipeline/", include("apps.file_pipeline.urls")),
    path("app/platform-api/", include("apps.platform_api.urls")),
    path("app/file-scheduler/", include("apps.file_scheduler.urls")),
    path("app/file-watch/", include("apps.file_watch.urls")),
    path("api/", include((api_urlpatterns, "platform_api_http"))),
    path("app/ayuda/", include(("apps.help.urls", "help"))),
]

if settings.DEBUG:
    from dynamicworkspace.prototype_serve import serve_prototype

    urlpatterns += [
        path("prototype/", serve_prototype),
        path("prototype/<path:relpath>", serve_prototype),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
