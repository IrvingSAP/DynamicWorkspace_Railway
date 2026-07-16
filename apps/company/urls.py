from django.urls import path

from apps.company import views

app_name = "company"

urlpatterns = [
    path("", views.company_list, name="list"),
    path("nueva/", views.company_create, name="create"),
    path("<uuid:pk>/", views.company_detail, name="detail"),
    path("<uuid:pk>/editar/", views.company_update, name="update"),
    path("<uuid:pk>/eliminar/", views.company_delete, name="delete"),
]
