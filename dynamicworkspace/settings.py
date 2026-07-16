"""
Django settings for dynamicworkspace project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)

DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# Django 4+ valida Origin/Referer en POST (fetch envía Origin).
# En local el navegador a veces manda http://127.0.0.1 sin puerto además de :8001.
_csrf_default_origins = []
for _host in ALLOWED_HOSTS:
    if "://" in _host:
        _csrf_default_origins.append(_host.rstrip("/"))
        continue
    for _scheme in ("http", "https"):
        _csrf_default_origins.append(f"{_scheme}://{_host}")
        for _port in ("8000", "8001", "8080"):
            _csrf_default_origins.append(f"{_scheme}://{_host}:{_port}")

CSRF_TRUSTED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        ",".join(_csrf_default_origins),
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.company",
    "apps.accounts",
    "apps.billing",
    "apps.public",
    "apps.security",
    "apps.dashboard",
    "apps.projects",
    "apps.fields",
    "apps.records",
    "apps.help",
    "apps.dms",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dynamicworkspace.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
            ],
        },
    },
]

WSGI_APPLICATION = "dynamicworkspace.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("sqlite"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "es-es"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/ingresar/"
LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "/ingresar/"

# Desarrollo (DEBUG=True): códigos de seguridad en la terminal del runserver.
# Producción: definir EMAIL_DELIVERY=resend y RESEND_API_KEY en el entorno.
if DEBUG:
    EMAIL_DELIVERY = "console"
else:
    EMAIL_DELIVERY = os.environ.get("EMAIL_DELIVERY", "resend")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "DynamicWorkspace <onboarding@resend.dev>")
PUBLIC_CONTACT_EMAIL = os.environ.get("PUBLIC_CONTACT_EMAIL", "contacto@dynamicworkspace.app")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

LICENSE_SECRET_KEY = os.environ.get("LICENSE_SECRET_KEY", SECRET_KEY)
