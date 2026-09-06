from django.urls import path

from apps.file_watch import views

app_name = "file_watch"

urlpatterns = [
    path("ayuda/", views.watch_guide, name="watch_guide"),
    path("errores/ayuda/", views.watch_errors_help, name="watch_errors_help"),
    path("errores/", views.watch_errors, name="watch_errors"),
    path("integracion/ayuda/", views.watch_integration_help, name="watch_integration_help"),
    path("integracion/", views.watch_integration, name="watch_integration"),
    path("bandejas/", views.watch_list, name="watch_list"),
    path("bandejas/ayuda/", views.watch_list_help, name="watch_list_help"),
    path("bandejas/nuevo/ayuda/", views.watch_create_help, name="watch_create_help"),
    path("bandejas/nuevo/", views.watch_create, name="watch_create"),
    path(
        "bandejas/<slug:watch_slug>/ayuda/",
        views.watch_hub_help,
        name="watch_hub_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/editar/ayuda/",
        views.watch_edit_help,
        name="watch_edit_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/editar/",
        views.watch_edit,
        name="watch_edit",
    ),
    path(
        "bandejas/<slug:watch_slug>/miembros/buscar/",
        views.watch_member_search,
        name="watch_member_search",
    ),
    path(
        "bandejas/<slug:watch_slug>/miembros/ayuda/",
        views.watch_members_help,
        name="watch_members_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/miembros/",
        views.watch_members,
        name="watch_members",
    ),
    path(
        "bandejas/<slug:watch_slug>/origen/ayuda/",
        views.watch_source_help,
        name="watch_source_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/origen/",
        views.watch_source,
        name="watch_source",
    ),
    path(
        "bandejas/<slug:watch_slug>/intake/ayuda/",
        views.watch_intake_help,
        name="watch_intake_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/intake/",
        views.watch_intake,
        name="watch_intake",
    ),
    path(
        "bandejas/<slug:watch_slug>/lotes/",
        views.watch_batches,
        name="watch_batches",
    ),
    path(
        "bandejas/<slug:watch_slug>/enrutado/proyectos/",
        views.watch_route_projects,
        name="watch_route_projects",
    ),
    path(
        "bandejas/<slug:watch_slug>/enrutado/ayuda/",
        views.watch_route_help,
        name="watch_route_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/enrutado/",
        views.watch_route,
        name="watch_route",
    ),
    path(
        "bandejas/<slug:watch_slug>/disparo/ayuda/",
        views.watch_fire_help,
        name="watch_fire_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/disparo/",
        views.watch_fire,
        name="watch_fire",
    ),
    path(
        "bandejas/<slug:watch_slug>/idempotencia/ayuda/",
        views.watch_idempotency_help,
        name="watch_idempotency_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/idempotencia/",
        views.watch_idempotency,
        name="watch_idempotency",
    ),
    path(
        "bandejas/<slug:watch_slug>/avisos/ayuda/",
        views.watch_notify_help,
        name="watch_notify_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/avisos/",
        views.watch_notify,
        name="watch_notify",
    ),
    path(
        "bandejas/<slug:watch_slug>/auditoria/ayuda/",
        views.watch_audit_help,
        name="watch_audit_help",
    ),
    path(
        "bandejas/<slug:watch_slug>/auditoria/",
        views.watch_audit,
        name="watch_audit",
    ),
    path(
        "bandejas/<slug:watch_slug>/push/",
        views.watch_api_push,
        name="watch_api_push",
    ),
    path(
        "bandejas/<slug:watch_slug>/modulo/<slug:module>/",
        views.watch_module_pending,
        name="watch_module_pending",
    ),
    path(
        "bandejas/<slug:watch_slug>/",
        views.watch_hub,
        name="watch_hub",
    ),
]
