# Estructura del proyecto

Referencia del **layout de carpetas** de DynamicWorkspace (chasis Django). Para replicar el árbol en un proyecto nuevo o saber dónde vive código vs docs vs prototipos.

**No** es el inventario de verticales. Producto y backlog: [`APP_FACTORY.md`](APP_FACTORY.md). Arquitectura y `apps/` instaladas: [`DynamicWorkspace.md`](DynamicWorkspace.md) §8.

---

## Árbol raíz

```
<proyecto>/
├── .cursor/
│   └── rules/              # Convenciones del agente (django, templates, UI)
├── .interface-design/      # Design system (tokens, system.md)
├── apps/                   # Apps Django (una carpeta = una app; ver DynamicWorkspace.md §8)
├── docs/                   # Ver § Documentación
├── dynamicworkspace/       # Proyecto Django (settings, production.py, urls, wsgi)
├── media/                  # Subidas de usuario (gitignore)
├── prototype/              # HTML estático de revisión UX (temporal)
│   └── <app>/
├── scripts/                # Utilidades de desarrollo (no runtime web)
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── app_base.html       # Layout zona privada /app/
│   ├── includes/
│   ├── <app>/
│   └── public/
├── test-assets/            # Fixtures locales (opcional)
├── .env.example
├── .gitignore
├── manage.py
├── railway.toml
├── Procfile
├── gunicorn.conf.py
├── README.md
└── requirements.txt
```

---

## Documentación (`docs/`)

| Ruta | Rol |
|------|-----|
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Chasis, dos motores, árbol Django, roadmap workspace |
| [`APP_FACTORY.md`](APP_FACTORY.md) | Índice verticales: hecho vs backlog |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Familia archivo §2 (Gate · Reverse · Match · Scout · Seed · Catalog) |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Ops: hecho §2 · backlog §4 |
| [`DataMappingStudio.md`](DataMappingStudio.md) | Motor FilePipe / ETL |
| `FILE_*.md` · `PLATFORM_API.md` · `PROFILE_SEED.md` · … | Producto por vertical / capa |
| [`definition_app/`](definition_app/README.md) | Chasis Django (company, accounts, projects, records, VISTAS, UI_MESSAGES) |
| `definition_app_<SLUG>/` | Specs **por módulo** de un vertical (DMS, FILE_GATE, PIPELINE, …) |
| [`security/`](security/SEGURIDAD_Y_ACCESOS.md) | Login, correo, 2FA |

Specs de pantalla de un vertical **no** van solo en `definition_app/<app>.md`: el patrón actual es carpeta `docs/definition_app_<SLUG>/` + doc de producto `docs/<PRODUCTO>.md`.

---

## Rol de cada capa

| Carpeta / archivo | Propósito | ¿Va a producción? |
|---------|-----------|-------------------|
| `apps/` | Lógica Django: `models`, `views`, `urls`, `services/`, `admin` | Sí |
| `templates/` | HTML con tags Django; hereda de `app_base` o `public/base` | Sí |
| `static/` | CSS/JS (WhiteNoise o CDN) | Sí |
| `dynamicworkspace/production.py` | Settings Railway (Postgres, `CONN_MAX_AGE`) | Sí (runtime prod) |
| `gunicorn.conf.py` / `railway.toml` / `Procfile` | Arranque y deploy | Sí (deploy) |
| `prototype/` | Maquetas UX antes de codificar | No (gitignore) |
| `docs/` | Definición funcional y convenciones | No (solo repo) |
| `.cursor/rules/` | Instrucciones del agente | Repo / no runtime |
| `scripts/` | Tareas de desarrollo | Repo / no runtime web |

---

## Convención por app Django

Mínimo:

```
apps/<nombre>/
├── apps.py
├── models.py          # si aplica
├── views.py           # o paquetes por módulo (p. ej. schema/, run/)
├── urls.py
├── admin.py           # si aplica
└── services/          # ok / error_code / user_message
```

Verticales grandes (Gate, Match, DMS, …) **parten** en subpaquetes (`projects/`, `schema/`, `run/`, …). Plantillas y estáticos **fuera** de `apps/`:

| Tipo | Ubicación |
|------|-----------|
| Templates | `templates/<app>/` |
| CSS | `static/css/<app>.css` o sección en `app.css` |
| JS | `static/js/` |

Mensajes: [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md).

---

## Flujo prototipo → producción

Igual ritual para chasis y verticales:

1. Spec: `docs/definition_app/<app>.md` **o** `docs/definition_app_<SLUG>/<modulo>.md` + producto `docs/<PRODUCTO>.md`
2. `prototype/<app>/…html`
3. Revisión UX → **OK**
4. `templates/<app>/` + vistas en `apps/<app>/`
5. Quitar prototipo (`prototype/README.md`)

Al abrir un vertical nuevo: criterio en [`APP_FACTORY.md`](APP_FACTORY.md) §4.

---

## Documentación mínima (chasis / exportar repo)

| Archivo | Contenido |
|---------|-----------|
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Visión, stack, fases workspace |
| [`APP_FACTORY.md`](APP_FACTORY.md) | Qué apps existen / qué falta |
| [`definition_app/README.md`](definition_app/README.md) | Índice chasis |
| [`definition_app/VISTAS.md`](definition_app/VISTAS.md) | Naming, URLs, DataTables |
| [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | Catálogo de mensajes |
| [`definition_app/CONVENCIONES.md`](definition_app/CONVENCIONES.md) | Reglas transversales |
| [`prototype/README.md`](../prototype/README.md) | Ciclo de prototipos |

---

## Reglas Cursor (`.cursor/rules/`)

| Archivo | Tema |
|---------|------|
| `django-conventions.mdc` | Sin Django Forms; `apps/` / `templates/` / `static/` |
| `templates-frontend.mdc` | Layout, DataTables, CSS |
| `ui-messages.mdc` | Mensajes y `error_code` |

---

## Checklist — nuevo proyecto (chasis vacío)

- [ ] Árbol raíz de arriba
- [ ] `django-admin startproject` → `dynamicworkspace/`
- [ ] Primera app `apps/core/` + `INSTALLED_APPS`
- [ ] `templates/app_base.html` + `static/css/app.css`
- [ ] `docs/definition_app/` con `README.md` y `VISTAS.md`
- [ ] `docs/DynamicWorkspace.md` + `docs/APP_FACTORY.md` (aunque el backlog esté vacío)
- [ ] `prototype/` con `README.md`
- [ ] `.cursor/rules/django-conventions.mdc`
- [ ] `.env.example` + `requirements.txt`

---

## Referencias

| Doc | Para qué |
|-----|----------|
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Arquitectura y lista de `apps/` |
| [`APP_FACTORY.md`](APP_FACTORY.md) | Verticales hecho / backlog; §4 criterio de vertical nuevo |
| [`definition_app/README.md`](definition_app/README.md) | Specs del chasis |
| [`prototype/README.md`](../prototype/README.md) | Prototipos |
