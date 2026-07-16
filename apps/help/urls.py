from django.urls import path

from apps.help import views

app_name = "help"

urlpatterns = [
    path("", views.uf_guide, name="uf_guide"),
]
