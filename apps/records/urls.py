from django.urls import path

from apps.records import views

app_name = "records"

urlpatterns = [
    path("", views.record_list, name="list"),
    path("expandir/", views.record_expand, name="expand"),
    path("expandir/apariencia/", views.record_expand_display, name="expand_display"),
    path("nuevo/", views.record_create, name="create"),
    path("<uuid:pk>/", views.record_detail, name="detail"),
    path("<uuid:pk>/editar/", views.record_update, name="update"),
]
