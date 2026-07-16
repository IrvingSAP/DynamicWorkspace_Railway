from django.urls import path

from apps.company.views import company_account
from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("bienvenida/", views.bienvenida, name="bienvenida"),
    path("accounts/", company_account, name="account"),
]