from django.urls import path

from apps.file_pipeline import views, views_catalog as catalog_views

app_name = "file_pipeline"

urlpatterns = [
    path("ayuda/", views.file_pipeline_guide, name="file_pipeline_guide"),
    path("tablero/ayuda/", views.pipeline_dashboard_help, name="pipeline_dashboard_help"),
    path("tablero/", views.pipeline_dashboard, name="pipeline_dashboard"),
    path("catalogo/", catalog_views.catalog_list, name="catalog_list"),
    path("catalogo/ayuda/", catalog_views.catalog_list_help, name="catalog_list_help"),
    path("catalogo/nuevo/", catalog_views.catalog_create, name="catalog_create"),
    path(
        "catalogo/nuevo/ayuda/",
        catalog_views.catalog_create_help,
        name="catalog_create_help",
    ),
    path(
        "catalogo/compania/",
        catalog_views.catalog_company,
        name="catalog_company",
    ),
    path(
        "catalogo/compania/ayuda/",
        catalog_views.catalog_company_help,
        name="catalog_company_help",
    ),
    path(
        "catalogo/<slug:kind>/ayuda/",
        catalog_views.catalog_detail_help,
        name="catalog_detail_help",
    ),
    path(
        "catalogo/<slug:kind>/editar/ayuda/",
        catalog_views.catalog_edit_help,
        name="catalog_edit_help",
    ),
    path(
        "catalogo/<slug:kind>/editar/",
        catalog_views.catalog_edit,
        name="catalog_edit",
    ),
    path(
        "catalogo/<slug:kind>/deshabilitar/",
        catalog_views.catalog_disable,
        name="catalog_disable",
    ),
    path(
        "catalogo/<slug:kind>/",
        catalog_views.catalog_detail,
        name="catalog_detail",
    ),
    path("pipelines/", views.pipeline_list, name="pipeline_list"),
    path("pipelines/ayuda/", views.pipeline_list_help, name="pipeline_list_help"),
    path("pipelines/nuevo/ayuda/", views.pipeline_create_help, name="pipeline_create_help"),
    path("pipelines/nuevo/", views.pipeline_create, name="pipeline_create"),
    path(
        "pipelines/<slug:pipeline_slug>/ayuda/",
        views.pipeline_hub_help,
        name="pipeline_hub_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/miembros/buscar/",
        views.pipeline_member_search,
        name="pipeline_member_search",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/miembros/ayuda/",
        views.pipeline_members_help,
        name="pipeline_members_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/miembros/",
        views.pipeline_members,
        name="pipeline_members",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/disenar/ayuda/",
        views.pipeline_designer_help,
        name="pipeline_designer_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/disenar/proyectos/",
        views.pipeline_designer_projects,
        name="pipeline_designer_projects",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/disenar/",
        views.pipeline_designer,
        name="pipeline_designer",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/publicar/ayuda/",
        views.pipeline_publish_help,
        name="pipeline_publish_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/publicar/",
        views.pipeline_publish,
        name="pipeline_publish",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/ejecutar/ayuda/",
        views.pipeline_run_help,
        name="pipeline_run_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/ejecutar/",
        views.pipeline_run,
        name="pipeline_run",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/runs/<uuid:run_id>/auditoria/ayuda/",
        views.pipeline_run_audit_help,
        name="pipeline_run_audit_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/runs/<uuid:run_id>/auditoria/",
        views.pipeline_run_audit,
        name="pipeline_run_audit",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/runs/<uuid:run_id>/eliminar/",
        views.pipeline_run_delete,
        name="pipeline_run_delete",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/runs/<uuid:run_id>/",
        views.pipeline_run_result,
        name="pipeline_run_result",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/historial/eliminar-mias/",
        views.pipeline_history_delete_own,
        name="pipeline_history_delete_own",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/historial/ayuda/",
        views.pipeline_history_help,
        name="pipeline_history_help",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/historial/",
        views.pipeline_history,
        name="pipeline_history",
    ),
    path(
        "pipelines/<slug:pipeline_slug>/",
        views.pipeline_hub,
        name="pipeline_hub",
    ),
]
