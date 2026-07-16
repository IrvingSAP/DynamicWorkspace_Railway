# apps.help

Guía general de **flujos de trabajo** para usuarios UF autenticados. Complementa la ayuda contextual por pantalla (`/app/proyectos/.../ayuda/`).

---

## Propósito

Orientar al usuario final (UF) en el recorrido completo del sistema: desde el panel de inicio hasta la consulta y exportación de registros. No describe campo a campo cada formulario; eso queda en las plantillas `project_*_help.html`, `field_*_help.html`, etc.

---

## Responsabilidades

| Sí | No |
|----|-----|
| Página estática de guía en `/app/ayuda/` | Ayuda contextual por pantalla (→ apps de dominio) |
| Enlaces a rutas reales del proyecto de ejemplo del usuario | CRUD ni lógica de negocio |
| Índice lateral de flujos (`guide-spine`) | Acceso para UA/US (solo UF) |

---

## Estructura

```
apps/help/
├── apps.py
├── views.py
└── urls.py

templates/help/
└── uf_guide.html

static/
├── css/help.css
└── js/guide-spine.js
```

**Prototipo origen:** `prototype/help/uf_guide.html` · **Estilos:** `prototype/help/help.css` → `static/css/help.css`

---

## URLs

| URL | Nombre | Vista | Acceso |
|-----|--------|-------|--------|
| `/app/ayuda/` | `help:uf_guide` | `uf_guide` | UF con sesión completa (`security_complete_required`) |

Montaje en `dynamicworkspace/urls.py`:

```python
path("app/ayuda/", include(("apps.help.urls", "help"))),
```

---

## Vista y contexto

`uf_guide` renderiza `help/uf_guide.html` con:

| Variable | Origen | Uso |
|----------|--------|-----|
| `profile` | `request.user.profile` | Datos del usuario |
| `company` | `profile.company` | Nombre corto en cabecera (`company.name_short`) |
| `example_project` | Primer `ProjectMembership` activa (proyecto no archivado, más reciente por `updated_at`) | Enlaces con `<slug>` en la guía |
| `app_nav_active` | `"help"` | Marca activa en `sidebar_uf.html` |

Si el usuario no tiene proyectos, los enlaces con slug hacen fallback a `projects:list`.

---

## Contenido de la guía (7 flujos)

| # | Flujo | Audiencia principal |
|---|-------|---------------------|
| 1 | Inicio y panel | Todos |
| 2 | Crear proyecto | PA |
| 3 | Diseñar campos | PA |
| 4 | Autorizar equipo | PA |
| 5 | Gestionar registros | PA, ED, CO |
| 6 | Vista expandida | Todos / PA (configuración) |
| 7 | Consulta y exportación | CO, GE, PA |

---

## Navegación

- **Sidebar UF:** `templates/includes/sidebar_uf.html` — ítem «Ayuda» → `{% url 'help:uf_guide' %}`
- **Plantilla base:** extiende `app_base.html` (zona `/app/`)

---

## Front-end

| Recurso | Descripción |
|---------|-------------|
| `static/css/help.css` | Layout guía, hero, tarjetas de flujo, spine lateral |
| `static/js/guide-spine.js` | Resalta el flujo visible al hacer scroll (compartido con guía pública) |

---

## Reglas

- Solo **UF** (`user_type_required(UserProfile.USER_FINAL)`).
- Sin modelos propios; app de presentación.
- Textos en español; ids/clases en inglés según convención del proyecto.

---

## Dependencias

- `apps.security` — decorador `security_complete_required`
- `apps.accounts` — `UserProfile`, tipos de usuario
- `apps.projects` — `ProjectMembership` para `example_project`

---

## Fase

**Fase 1** — implementado.

## Documentos relacionados

- [`dashboard.md`](dashboard.md) — menú UF y enlace Ayuda
- [`public.md`](public.md) — guía equivalente para visitantes sin cuenta (`/ayuda/`)
- [`projects.md`](projects.md) — ayuda contextual por proyecto
- Prototipo: [`../../prototype/help/uf_guide.html`](../../prototype/help/uf_guide.html)
