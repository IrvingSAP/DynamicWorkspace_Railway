from django.urls import path

from apps.fields import views

app_name = "fields"

urlpatterns = [
    path("", views.field_list, name="list"),
    path("nuevo/", views.field_create, name="create"),
    path("<uuid:pk>/editar/", views.field_update, name="update"),
]
