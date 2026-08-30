from django.urls import path

from apps.help import views

app_name = "help"

urlpatterns = [
    path("", views.uf_guide, name="uf_guide"),
    path("us/manuales/jobs/", views.us_manual_jobs, name="us_manual_jobs"),
    path("us/manuales/pipelines/", views.us_manual_pipelines, name="us_manual_pipelines"),
    path("us/<slug:topic>/", views.us_general_guide, name="us_general_guide"),
]
