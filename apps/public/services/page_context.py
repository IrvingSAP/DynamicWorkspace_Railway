from django.conf import settings


def public_page_context(nav_active: str) -> dict:
    return {
        "nav_active": nav_active,
        "login_url": "/ingresar/",
        "contact_email": getattr(
            settings,
            "PUBLIC_CONTACT_EMAIL",
            "sistemaasociados@gmail.com",
        ),
    }
