# Estructura del proyecto

Referencia para replicar el layout de DynamicWorkspace en un proyecto nuevo.

---

## Árbol raíz

```
<proyecto>/
├── .cursor/
│   └── rules/              # Reglas del agente Cursor (convenciones, UI, templates)
├── .interface-design/        # Design system (tokens, system.md)
├── apps/                     # Apps Django de negocio (una carpeta = una app)
├── docs/
│   ├── ESTRUCTURA_PROYECTO.md   # Este archivo
│   ├── DynamicWorkspace.md      # Visión de producto y arquitectura
│   ├── definition_app/          # Un .md por app (modelos, URLs, reglas)
│   └── security/                # Flujos e implementación de seguridad
├── dynamicworkspace/           # Proyecto Django (settings, urls, wsgi)
├── media/                      # Subidas de usuario (gitignore)
├── prototype/                  # HTML estático de revisión UX (temporal)
│   └── <app>/                  # Misma convención de nombres que templates/
├── scripts/                    # Utilidades puntuales (tests manuales, migraciones aux.)
├── static/
│   ├── css/                    # Estilos por app o globales (app.css, public.css…)
│   └── js/                     # Scripts por pantalla o compartidos
├── templates/
│   ├── app_base.html           # Layout zona privada /app/
│   ├── includes/               # Parciales (sidebars, nav, mensajes)
│   ├── <app>/                  # Plantillas Django finales
│   └── public/                 # Sitio público (base.html, home, contacto…)
├── test-assets/                # Fixtures para pruebas locales (opcional)
├── .env.example
├── .gitignore
├── manage.py
├── railway.toml                # Deploy (opcional)
├── README.md
└── requirements.txt
```

---

## Rol de cada capa

| Carpeta | Propósito | ¿Va a producción? |
|---------|-----------|-------------------|
| `apps/` | Lógica Django: `models`, `views`, `urls`, `services/`, `admin` | Sí |
| `templates/` | HTML con tags Django; hereda de `app_base` o `public/base` | Sí |
| `static/` | CSS/JS servidos por WhiteNoise o CDN | Sí |
| `prototype/` | Maquetas estáticas para validar UX antes de codificar | No |
| `docs/` | Definición funcional, modelo de datos, convenciones | No (solo repo) |
| `.cursor/rules/` | Instrucciones persistentes para el agente | No (solo repo) |
| `scripts/` | Tareas de desarrollo; no son parte del runtime web | No |

---

## Convención por app Django

```
apps/<nombre>/
├── apps.py
├── models.py          # si aplica
├── views.py
├── urls.py
├── admin.py           # si aplica
└── services/          # validación y negocio (retorno ok/error_code)
    └── *_service.py
```

Plantillas y estáticos **no** viven dentro de `apps/`:

| Tipo | Ubicación |
|------|-----------|
| Templates | `templates/<app>/` |
| CSS | `static/css/<app>.css` o sección en `app.css` |
| JS | `static/js/` |

---

## Flujo prototipo → producción

1. Definir pantalla en `docs/definition_app/<app>.md`
2. Crear `prototype/<app>/<app>_<accion>.html`
3. Revisar y marcar **OK**
4. Migrar a `templates/<app>/` + vista en `apps/<app>/views.py`
5. Eliminar prototipo (ver `prototype/README.md`)

---

## Documentación mínima al exportar

| Archivo | Contenido |
|---------|-----------|
| `docs/DynamicWorkspace.md` | Visión, stack, fases |
| `docs/definition_app/README.md` | Índice de apps |
| `docs/definition_app/VISTAS.md` | Naming, URLs, DataTables, layout |
| `docs/definition_app/UI_MESSAGES.md` | Catálogo de mensajes |
| `docs/definition_app/CONVENCIONES.md` | Reglas transversales |
| `prototype/README.md` | Ciclo de vida de prototipos |

---

## Reglas Cursor recomendadas (`.cursor/rules/`)

| Archivo | Tema |
|---------|------|
| `django-conventions.mdc` | Sin Django Forms, estructura apps/templates/static |
| `templates-frontend.mdc` | Layout, DataTables, clases CSS |
| `ui-messages.mdc` | Mensajes y `error_code` en vistas/servicios |

---

## Checklist — nuevo proyecto

- [ ] Crear repo con árbol raíz de arriba
- [ ] `django-admin startproject` → carpeta `dynamicworkspace/`
- [ ] Primera app en `apps/core/` + `INSTALLED_APPS`
- [ ] `templates/app_base.html` + `static/css/app.css`
- [ ] `docs/definition_app/` con al menos `README.md` y `VISTAS.md`
- [ ] `prototype/` vacío con `README.md`
- [ ] `.cursor/rules/django-conventions.mdc`
- [ ] `.env.example` + `requirements.txt`

---

## Referencias

- Prototipos: [`prototype/README.md`](../prototype/README.md)
- Apps: [`definition_app/README.md`](definition_app/README.md)
- Arquitectura: [`DynamicWorkspace.md`](DynamicWorkspace.md)
