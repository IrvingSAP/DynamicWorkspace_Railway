from django.urls import path

from apps.dms.catalogs import views

urlpatterns = [
    path("", views.hub, name="catalog_hub"),
    path("ayuda/", views.hub_help, name="catalog_hub_help"),
    path("<slug:catalog_slug>/ayuda/", views.list_help, name="catalog_list_help"),
    path(
        "<slug:catalog_slug>/formulario/ayuda/",
        views.form_help,
        name="catalog_form_help",
    ),
    path("<slug:catalog_slug>/", views.list_view, name="catalog_list"),
    path("<slug:catalog_slug>/nuevo/", views.create, name="catalog_create"),
    path(
        "<slug:catalog_slug>/<uuid:pk>/editar/",
        views.update,
        name="catalog_update",
    ),
    path(
        "<slug:catalog_slug>/<uuid:pk>/desactivar/",
        views.deactivate,
        name="catalog_deactivate",
    ),
]
