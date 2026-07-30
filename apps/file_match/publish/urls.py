from django.urls import path

from apps.file_match.publish import views

urlpatterns = [
    path("", views.hub, name="publish_hub"),
    path("ayuda/", views.hub_help, name="publish_hub_help"),
    path("ejecutar/", views.publish_action, name="publish_action"),
]
