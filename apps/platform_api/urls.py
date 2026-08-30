from django.urls import path

from apps.platform_api import api_views, views

app_name = "platform_api"

urlpatterns = [
    path("clientes/", views.client_list, name="client_list"),
    path("clientes/ayuda/", views.client_list_help, name="client_list_help"),
    path("clientes/nuevo/", views.client_create, name="client_create"),
    path("clientes/nuevo/ayuda/", views.client_create_help, name="client_create_help"),
    path("seguridad/", views.security_policy, name="security_policy"),
    path("seguridad/ayuda/", views.security_policy_help, name="security_policy_help"),
    path("contrato/", views.contract_guide, name="contract_guide"),
    path("contrato/ayuda/", views.contract_guide_help, name="contract_guide_help"),
    path("openapi/", views.openapi_guide, name="openapi_guide"),
    path("openapi/ayuda/", views.openapi_guide_help, name="openapi_guide_help"),
    path("integracion/", views.integration_guide, name="integration_guide"),
    path("integracion/ayuda/", views.integration_guide_help, name="integration_guide_help"),
    path("auditoria/", views.audit_list, name="audit_list"),
    path("auditoria/ayuda/", views.audit_list_help, name="audit_list_help"),
    path("auditoria/<uuid:pk>/", views.audit_event, name="audit_event"),
    path("auditoria/<uuid:pk>/ayuda/", views.audit_event_help, name="audit_event_help"),
    path("clientes/<uuid:pk>/key/", views.client_reveal, name="client_reveal"),
    path(
        "clientes/<uuid:pk>/key/ayuda/",
        views.client_reveal_help,
        name="client_reveal_help",
    ),
    path("clientes/<uuid:pk>/auditoria/", views.client_audit, name="client_audit"),
    path(
        "clientes/<uuid:pk>/auditoria/ayuda/",
        views.client_audit_help,
        name="client_audit_help",
    ),
    path("clientes/<uuid:pk>/ayuda/", views.client_detail_help, name="client_detail_help"),
    path("clientes/<uuid:pk>/", views.client_detail, name="client_detail"),
    path("clientes/<uuid:pk>/webhook/", views.client_webhook, name="client_webhook"),
    path("clientes/<uuid:pk>/rotar/", views.client_rotate, name="client_rotate"),
    path("clientes/<uuid:pk>/revocar/", views.client_revoke, name="client_revoke"),
]

api_urlpatterns = [
    path("v1/whoami", api_views.whoami, name="whoami"),
    path("v1/contract", api_views.contract_catalog, name="contract_catalog"),
    path("v1/openapi", api_views.openapi_catalog, name="openapi_catalog"),
    path("v1/integration", api_views.integration_catalog, name="integration_catalog"),
    path("v1/jobs/validate", api_views.jobs_validate, name="jobs_validate"),
    path("v1/jobs/run", api_views.jobs_run, name="jobs_run"),
    path("v1/jobs", api_views.jobs_list, name="jobs_list"),
    path("v1/jobs/<uuid:job_id>/report", api_views.jobs_report, name="jobs_report"),
    path("v1/jobs/<uuid:job_id>/output", api_views.jobs_output, name="jobs_output"),
    path("v1/jobs/<uuid:job_id>/cancel", api_views.jobs_cancel, name="jobs_cancel"),
    path("v1/jobs/<uuid:job_id>", api_views.jobs_detail, name="jobs_detail"),
    path(
        "v1/pipelines/<slug:pipeline_id>/runs",
        api_views.pipeline_runs,
        name="pipeline_runs",
    ),
]
