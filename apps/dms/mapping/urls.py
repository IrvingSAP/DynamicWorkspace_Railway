from django.urls import path

from apps.dms.mapping import views

urlpatterns = [
    path("", views.project_list, name="mapping_list"),
    path("ayuda/", views.project_list_help, name="mapping_list_help"),
    path("nuevo/ayuda/", views.project_create_help, name="mapping_create_help"),
    path("nuevo/", views.project_create, name="mapping_create"),
    path("<slug:project_slug>/ayuda/", views.project_hub_help, name="mapping_hub_help"),
    path("<slug:project_slug>/miembros/ayuda/", views.project_members_help, name="mapping_members_help"),
    path("<slug:project_slug>/", views.project_hub, name="mapping_hub"),
    path("<slug:project_slug>/miembros/", views.project_members, name="mapping_members"),
]
