"""Gunicorn — solo producción (Railway). Uso: gunicorn -c gunicorn.conf.py …"""

from __future__ import annotations

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# gthread: mejor para Django con I/O (DB, Resend, filesystem).
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
workers = int(os.environ.get("WEB_CONCURRENCY", os.environ.get("GUNICORN_WORKERS", "3")))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

# Reciclado de workers para limitar fugas de memoria.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "50"))

accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

preload_app = os.environ.get("GUNICORN_PRELOAD", "false").lower() in ("1", "true", "yes")
