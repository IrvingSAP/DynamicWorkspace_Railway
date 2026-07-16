# apps.public

Sitio público sin autenticación: inicio, servicios, contacto y **guía de flujos** para visitantes.

---

## Propósito

Presentar el producto a prospectos y ofrecer una guía narrativa del sistema antes del login. Las cuentas se habilitan por administración (UA/US); no hay registro público.

---

## Responsabilidades

| Sí | No |
|----|-----|
| Páginas marketing en `/`, `/servicios/`, `/contacto/`, `/ayuda/` | Login ni zona `/app/` |
| Formulario de contacto (servicio + envío) | Gestión de leads en base de datos (Fase posterior) |
| Guía de flujos para visitantes | Enlaces internos con slug de proyecto |

---

## Estructura

```
apps/public/
├── apps.py
├── views.py
├── urls.py
└── services/
    ├── contact.py
    └── page_context.py

templates/public/
├── home.html
├── services.html
├── contact.html
└── help.html

templates/includes/
├── public_nav.html
└── public_footer.html

static/css/public.css   # incluye estilos de guía pública
static/js/guide-spine.js
```

**Prototipo guía:** `prototype/public/public_help.html` → `templates/public/help.html`

---

## URLs

| URL | Nombre | Vista | Descripción |
|-----|--------|-------|-------------|
| `/` | `public:home` | `home` | Landing |
| `/servicios/` | `public:services` | `services` | Capacidades del producto |
| `/ayuda/` | `public:help` | `help_guide` | Guía de flujos (visitantes) |
| `/contacto/` | `public:contact` | `contact` | Formulario de contacto |

Montaje en `dynamicworkspace/urls.py` (raíz del sitio, fuera de `/app/`).

---

## Guía pública (`/ayuda/`)

Misma estructura de **7 flujos** que la guía UF, con tono comercial y sin enlaces a pantallas internas autenticadas.

| Aspecto | Guía pública | Guía UF (`apps.help`) |
|---------|--------------|------------------------|
| URL | `/ayuda/` | `/app/ayuda/` |
| Audiencia | Visitantes | Usuarios UF logueados |
| Enlaces | Inicio, servicios, contacto, login | Dashboard, proyectos, campos, registros (con slug) |
| Plantilla | `public/help.html` | `help/uf_guide.html` |
| Layout | `public_base` + `public.css` | `app_base` + `help.css` |

**Navegación:** `public_nav.html`, `public_footer.html`, CTA en `home.html` («Guía del sistema»).

**Contexto:** `public_page_context("help")` — `nav_active`, `login_url`, `contact_email`.

---

## Servicios

### `page_context.py`

Devuelve contexto común de navegación pública (`nav_active`, URLs de login y correo de contacto desde `PUBLIC_CONTACT_EMAIL`).

### `contact.py`

Valida y envía el mensaje del formulario de contacto (`submit_contact_message`). Errores y mensajes de éxito según [`UI_MESSAGES.md`](UI_MESSAGES.md).

---

## Front-end

| Recurso | Uso |
|---------|-----|
| `static/css/public.css` | Layout público + sección guía (`.pub-guide-*`, `.pub-section-tight-top`) |
| `static/js/guide-spine.js` | Índice lateral con scroll spy (compartido con UF) |

---

## Reglas

- Sin autenticación requerida.
- Sin modelos Django en esta app (contacto vía servicio/correo).
- Coherencia de mensajes con [`UI_MESSAGES.md`](UI_MESSAGES.md) en contacto.

---

## Dependencias

- `apps.core` — configuración (`PUBLIC_CONTACT_EMAIL`)
- Resend u otro backend de correo (vía servicio de contacto)

---

## Fase

**Fase 0** (páginas estáticas y contacto) · **Guía de flujos:** implementada en Fase 1.

## Documentos relacionados

- [`help.md`](help.md) — guía UF autenticada
- [`dashboard.md`](dashboard.md) — zona privada `/app/`
- [`security.md`](security.md) — login `/ingresar/`
- Prototipo: [`../../prototype/public/public_help.html`](../../prototype/public/public_help.html)
