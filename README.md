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
├── dynamicworkspace/   # Configuración del proyecto Django
├── apps/               # Apps de negocio
├── templates/          # Plantillas HTML
├── static/css|js/      # Assets estáticos
├── prototype/          # Prototipos HTML (revisión UX)
├── docs/               # Documentación funcional y técnica
├── .cursor/rules/      # Reglas del agente
├── manage.py
└── requirements.txt
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

## Convenciones

- Los formularios se implementan en HTML plano; no usar `django.forms`.
- Las reglas de Cursor viven en `.cursor/rules/`.
