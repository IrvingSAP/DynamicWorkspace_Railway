from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.account_list, name="list"),
    path("nuevo/", views.account_create, name="create"),
    path("<uuid:pk>/", views.account_detail, name="detail"),
    path("<uuid:pk>/editar/", views.account_update, name="update"),
    path("<uuid:pk>/contraseña/", views.account_password, name="password"),
    path("<uuid:pk>/eliminar/", views.account_delete, name="delete"),
]
