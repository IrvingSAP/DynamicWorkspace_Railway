from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("planes/", views.plan_list, name="plan_list"),
    path("planes/nuevo/", views.plan_create, name="plan_create"),
    path("planes/<uuid:pk>/", views.plan_detail, name="plan_detail"),
    path("planes/<uuid:pk>/editar/", views.plan_update, name="plan_update"),
    path("planes/<uuid:pk>/eliminar/", views.plan_delete, name="plan_delete"),
    path("suscripciones/", views.subscription_list, name="subscription_list"),
    path("suscripciones/nueva/", views.subscription_create, name="subscription_create"),
    path(
        "suscripciones/<uuid:company_pk>/",
        views.subscription_detail,
        name="subscription_detail",
    ),
    path(
        "suscripciones/<uuid:company_pk>/editar/",
        views.subscription_update,
        name="subscription_update",
    ),
    path(
        "suscripciones/<uuid:company_pk>/eliminar/",
        views.subscription_delete,
        name="subscription_delete",
    ),
    path("pagos/", views.payment_list, name="payment_list"),
    path("pagos/nuevo/", views.payment_create, name="payment_create"),
    path("pagos/<uuid:pk>/", views.payment_detail, name="payment_detail"),
]
