from django.urls import path

from apps.security import views

app_name = "security"

urlpatterns = [
    path("ingresar/", views.login_view, name="login"),
    path("seguridad/correo/", views.email_code_view, name="email_code"),
    path("seguridad/totp-config/", views.totp_setup_view, name="totp_setup"),
    path("seguridad/totp/", views.totp_view, name="totp"),
    path("seguridad/actualizar-2fa/", views.actualizar_2fa_view, name="actualizar_2fa"),
    path("seguridad/cancelar/", views.cancel_view, name="cancel"),
    path("salir/", views.logout_view, name="logout"),
]
