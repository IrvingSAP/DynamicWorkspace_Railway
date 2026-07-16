"""
Settings de producción (Railway).

Activar solo en deploy:
  DJANGO_SETTINGS_MODULE=dynamicworkspace.production

Desarrollo local sigue usando dynamicworkspace.settings (runserver / DEBUG).
"""

from __future__ import annotations

import os
import sys

import dj_database_url

from dynamicworkspace.settings import *  # noqa: F403

# Producción por defecto: DEBUG off (override explícito con DEBUG=true si hace falta).
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

if DEBUG:
    EMAIL_DELIVERY = "console"
else:
    EMAIL_DELIVERY = os.environ.get("EMAIL_DELIVERY", "resend")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
_is_collectstatic = len(sys.argv) >= 2 and sys.argv[1] == "collectstatic"

if _is_collectstatic and (not DATABASE_URL or DATABASE_URL.startswith("sqlite")):
    # Build Nixpacks: collectstatic no necesita PostgreSQL.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
elif not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "dynamicworkspace.production requiere DATABASE_URL PostgreSQL "
        "(p. ej. la que inyecta Railway). No use SQLite en producción."
    )
else:
    # Reutiliza conexiones PG entre requests (menos latencia). Health checks
    # descartan conexiones muertas tras idle / restart del pooler.
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=int(os.environ.get("CONN_MAX_AGE", "600")),
            conn_health_checks=True,
            ssl_require=os.environ.get("DATABASE_SSL_REQUIRE", "true").lower()
            in ("1", "true", "yes"),
        )
    }

# Railway termina TLS en el proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in ("1", "true", "yes"):
    SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
