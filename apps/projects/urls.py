from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("ayuda/", views.project_list_help, name="list_help"),
    path("nuevo/", views.project_create, name="create"),
    path("nuevo/ayuda/", views.project_create_help, name="create_help"),
    path("<slug:slug>/ayuda/", views.project_detail_help, name="detail_help"),
    path("<slug:slug>/miembros/ayuda/", views.project_members_help, name="members_help"),
    path("<slug:slug>/miembros/", views.project_members, name="members"),
    path("<slug:slug>/", views.project_detail, name="detail"),
]
