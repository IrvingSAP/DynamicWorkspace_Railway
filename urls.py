from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

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
    path("app/ayuda/", include(("apps.help.urls", "help"))),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
