from django.urls import path

from apps.file_scheduler import views

app_name = "file_scheduler"

urlpatterns = [
    path("ayuda/", views.schedule_guide, name="schedule_guide"),
    path("planes/", views.schedule_list, name="schedule_list"),
    path("planes/ayuda/", views.schedule_list_help, name="schedule_list_help"),
    path("errores/ayuda/", views.schedule_errors_help, name="schedule_errors_help"),
    path("errores/", views.schedule_errors, name="schedule_errors"),
    path("integracion/ayuda/", views.schedule_integration_help, name="schedule_integration_help"),
    path("integracion/", views.schedule_integration, name="schedule_integration"),
    path("planes/nuevo/ayuda/", views.schedule_create_help, name="schedule_create_help"),
    path("planes/nuevo/", views.schedule_create, name="schedule_create"),
    path(
        "planes/<slug:schedule_slug>/ayuda/",
        views.schedule_hub_help,
        name="schedule_hub_help",
    ),
    path(
        "planes/<slug:schedule_slug>/editar/ayuda/",
        views.schedule_edit_help,
        name="schedule_edit_help",
    ),
    path(
        "planes/<slug:schedule_slug>/editar/",
        views.schedule_edit,
        name="schedule_edit",
    ),
    path(
        "planes/<slug:schedule_slug>/miembros/buscar/",
        views.schedule_member_search,
        name="schedule_member_search",
    ),
    path(
        "planes/<slug:schedule_slug>/miembros/ayuda/",
        views.schedule_members_help,
        name="schedule_members_help",
    ),
    path(
        "planes/<slug:schedule_slug>/miembros/",
        views.schedule_members,
        name="schedule_members",
    ),
    path(
        "planes/<slug:schedule_slug>/programacion/preview/",
        views.schedule_cron_preview,
        name="schedule_cron_preview",
    ),
    path(
        "planes/<slug:schedule_slug>/programacion/ayuda/",
        views.schedule_cron_help,
        name="schedule_cron_help",
    ),
    path(
        "planes/<slug:schedule_slug>/programacion/",
        views.schedule_cron,
        name="schedule_cron",
    ),
    path(
        "planes/<slug:schedule_slug>/destino/proyectos/",
        views.schedule_target_projects,
        name="schedule_target_projects",
    ),
    path(
        "planes/<slug:schedule_slug>/destino/ayuda/",
        views.schedule_target_help,
        name="schedule_target_help",
    ),
    path(
        "planes/<slug:schedule_slug>/destino/",
        views.schedule_target,
        name="schedule_target",
    ),
    path(
        "planes/<slug:schedule_slug>/solape/ayuda/",
        views.schedule_overlap_help,
        name="schedule_overlap_help",
    ),
    path(
        "planes/<slug:schedule_slug>/solape/",
        views.schedule_overlap,
        name="schedule_overlap",
    ),
    path(
        "planes/<slug:schedule_slug>/avisos/ayuda/",
        views.schedule_notify_help,
        name="schedule_notify_help",
    ),
    path(
        "planes/<slug:schedule_slug>/avisos/",
        views.schedule_notify,
        name="schedule_notify",
    ),
    path(
        "planes/<slug:schedule_slug>/dependencia/ayuda/",
        views.schedule_dependency_help,
        name="schedule_dependency_help",
    ),
    path(
        "planes/<slug:schedule_slug>/dependencia/",
        views.schedule_dependency,
        name="schedule_dependency",
    ),
    path(
        "planes/<slug:schedule_slug>/actividad/ayuda/",
        views.schedule_activity_help,
        name="schedule_activity_help",
    ),
    path(
        "planes/<slug:schedule_slug>/actividad/",
        views.schedule_activity,
        name="schedule_activity",
    ),
    path(
        "planes/<slug:schedule_slug>/auditoria/ayuda/",
        views.schedule_audit_help,
        name="schedule_audit_help",
    ),
    path(
        "planes/<slug:schedule_slug>/auditoria/",
        views.schedule_audit,
        name="schedule_audit",
    ),
    path(
        "planes/<slug:schedule_slug>/modulo/<slug:module>/",
        views.schedule_module_pending,
        name="schedule_module_pending",
    ),
    path(
        "planes/<slug:schedule_slug>/",
        views.schedule_hub,
        name="schedule_hub",
    ),
]
