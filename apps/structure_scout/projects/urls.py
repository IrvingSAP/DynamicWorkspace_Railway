from django.urls import path

from apps.structure_scout.projects import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("ayuda/", views.project_list_help, name="project_list_help"),
    path("nuevo/ayuda/", views.project_create_help, name="project_create_help"),
    path("nuevo/", views.project_create, name="project_create"),
    path("<slug:project_slug>/ayuda/", views.project_hub_help, name="project_hub_help"),
    path(
        "<slug:project_slug>/miembros/ayuda/",
        views.project_members_help,
        name="project_members_help",
    ),
    path("<slug:project_slug>/miembros/", views.project_members, name="project_members"),
    path("<slug:project_slug>/", views.project_hub, name="project_hub"),
]
