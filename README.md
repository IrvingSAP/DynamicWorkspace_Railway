# DynamicWorkspace

Aplicación web con Django, HTML, JavaScript y CSS.

## Stack

- **Backend:** Python + Django
- **Frontend:** Templates HTML, JavaScript, CSS (sin Django Forms)
- **Email:** Resend (producción); en desarrollo los códigos de seguridad van a la terminal (`EMAIL_DELIVERY=console` con `DEBUG=True`)
- **Deploy:** Railway (`dynamicworkspace.production`, Gunicorn `gthread`, `CONN_MAX_AGE`)

## Estructura

Árbol completo y guía para replicar en otro proyecto: [`docs/ESTRUCTURA_PROYECTO.md`](docs/ESTRUCTURA_PROYECTO.md).

```
DynamicWorkspace/
├── dynamicworkspace/   # Configuración del proyecto Django (+ production.py)
├── apps/               # Apps de negocio
├── templates/          # Plantillas HTML
├── static/css|js/      # Assets estáticos
├── docs/               # Documentación funcional y técnica
├── scripts/            # Utilidades
├── manage.py
├── requirements.txt
├── railway.toml
├── Procfile
└── gunicorn.conf.py
```

## Desarrollo local

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # Ajustar variables
python manage.py migrate
python manage.py runserver
```

### Correo en desarrollo (solo pruebas locales)

Con `DEBUG=True` (valor por defecto en `.env`), Django **no envía correos reales**: los códigos de verificación de seguridad se imprimen en la **misma terminal** donde corre `runserver`. No necesitas buzones de prueba para el onboarding de correo + 2FA.

- Pantalla: `/seguridad/correo/` tras el primer login.
- Busca en la terminal: `Tu código de verificación DynamicWorkspace es: XXXXXX`.
- En producción (`DEBUG=False`) aplica Resend; ver `docs/security/GUIA_IMPLEMENTACION_SEGURIDAD.md` §5.3.

## Deploy Railway (producción)

Aplica **solo en producción**. Local sigue con `dynamicworkspace.settings` + `runserver`.

Settings module en Railway:

`DJANGO_SETTINGS_MODULE=dynamicworkspace.production`

### Piezas de configuración

| Pieza | Qué hace |
|-------|----------|
| `gunicorn.conf.py` | Worker `gthread`; por defecto 3 procesos × 2 hilos (= 6 requests simultáneos); timeouts, reciclado de workers y logs vía variables de entorno |
| `dynamicworkspace/production.py` | PostgreSQL vía `DATABASE_URL`; `CONN_MAX_AGE=600` + `CONN_HEALTH_CHECKS` (reutiliza conexiones y reduce latencia); SSL proxy / cookies seguras |
| `railway.toml` | `collectstatic` en **build** (una vez por deploy); `migrate` en **release**; `startCommand` solo Gunicorn `-c gunicorn.conf.py` |
| `Procfile` | Mismo arranque web/release para Railway |
| `requirements.txt` | Incluye `gunicorn`, `whitenoise`, `dj-database-url`, `psycopg[binary]`, `resend` |

### Variables de entorno obligatorias en Railway

| Variable | Valor / nota |
|----------|----------------|
| `DJANGO_SETTINGS_MODULE` | `dynamicworkspace.production` (también lo fija `railway.toml` / `Procfile`) |
| `DEBUG` | `False` |
| `SECRET_KEY` | Secreto fuerte (no el default de desarrollo) |
| `DATABASE_URL` | PostgreSQL (Railway lo inyecta al enlazar el servicio) |
| `ALLOWED_HOSTS` | Dominio(s) del servicio Railway |
| `CSRF_TRUSTED_ORIGINS` | `https://…` del dominio Railway |
| `RESEND_API_KEY` | API key de Resend |
| `EMAIL_DELIVERY` | `resend` (default en producción si `DEBUG=False`) |
| `DEFAULT_FROM_EMAIL` | Remitente con dominio verificado en Resend |

### Variables opcionales (rendimiento / Gunicorn)

| Variable | Default | Uso |
|----------|---------|-----|
| `CONN_MAX_AGE` | `600` | Segundos de reutilización de conexión PostgreSQL |
| `DATABASE_SSL_REQUIRE` | `true` | SSL hacia Postgres |
| `WEB_CONCURRENCY` / `GUNICORN_WORKERS` | `3` | Procesos worker |
| `GUNICORN_THREADS` | `2` | Hilos por worker (`gthread`) |
| `GUNICORN_TIMEOUT` | `120` | Timeout de request |
| `GUNICORN_MAX_REQUESTS` | `1000` | Reciclado de workers |
| `GUNICORN_LOG_LEVEL` | `info` | Nivel de log |
| `SECURE_SSL_REDIRECT` | `true` | Redirección HTTPS detrás del proxy Railway |

### Flujo de deploy

1. Push a `main` en GitHub → Railway construye con Nixpacks.
2. **Build:** `collectstatic --noinput` (con settings de producción).
3. **Release:** `migrate --noinput`.
4. **Start:** Gunicorn con `gunicorn.conf.py` (sin correr `collectstatic` en cada arranque).

Detalle de variables de ejemplo: `.env.example` (bloque «Producción (Railway)»).

## Repositorio GitHub (primer push)

Remoto de producción / Railway:

`https://github.com/IrvingSAP/DynamicWorkspace_Railway.git`

### Orden recomendado (primera vez)

```bash
git remote add origin https://github.com/IrvingSAP/DynamicWorkspace_Railway.git

git add .gitignore .env.example README.md requirements.txt railway.toml Procfile gunicorn.conf.py manage.py dynamicworkspace apps templates static docs scripts
git status
git commit -m "Initial DynamicWorkspace project setup"
git branch -M main
git push -u origin main
```

### Qué se versiona (y qué no)

| Incluir | No incluir (`.gitignore`) |
|---------|---------------------------|
| `apps/`, `dynamicworkspace/`, `templates/`, `static/`, `docs/`, `scripts/` | `.env`, `db.sqlite3`, `media/`, `staticfiles/`, `.venv/` |
| `requirements.txt`, `railway.toml`, `Procfile`, `gunicorn.conf.py` | `.cursor/`, `.agents/`, `.interface-design/`, `prototype/`, `test-assets/` |
| `.gitignore`, `.env.example`, `README.md`, `manage.py` | Notas locales (`Ideas.txt`, `Data Mapping Studio.txt`, `skills-lock.json`) |

**No subir** archivos Django duplicados en la raíz (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `__init__.py`): el proyecto real está en `dynamicworkspace/`.

### Cambios posteriores

```bash
git add <archivos>
git status
git commit -m "Descripción del cambio"
git push
```

Si `origin` ya existe y hay que corregir la URL:

```bash
git remote set-url origin https://github.com/IrvingSAP/DynamicWorkspace_Railway.git
```

## Convenciones

- Los formularios se implementan en HTML plano; no usar `django.forms`.
- Las reglas de Cursor viven en `.cursor/rules/` (local; no se versionan en este repo).
