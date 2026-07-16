from django.urls import path

from apps.public import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("servicios/", views.services, name="services"),
    path("ayuda/", views.help_guide, name="help"),
    path("contacto/", views.contact, name="contact"),
]
