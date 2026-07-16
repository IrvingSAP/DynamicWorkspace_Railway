# Convenciones — todas las apps

Reglas transversales para el desarrollo de DynamicWorkspace. Las reglas de Cursor en `.cursor/rules/` (`django-conventions.mdc`, `ui-messages.mdc`, `templates-frontend.mdc`) deben alinearse con este documento.

---

## 1. Stack y restricciones

| Regla | Detalle |
|-------|---------|
| Sin Django Forms | No usar `forms.py`, `ModelForm`, widgets de Django |
| Formularios HTML | Templates en `templates/`; procesamiento en vistas |
| Validación | Manual en servicios o vistas; capa `validators/` por tipo de campo |
| Frontend | CSS en `static/css/`, JS en `static/js/` |
| Idioma código | Variables, funciones y clases en inglés |
| Idioma docs | Español |

---

## 2. Estructura de apps

Ver también [`VISTAS.md`](VISTAS.md) — reglas detalladas para `views.py`.

```
apps/
├── <app_name>/
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── services/       # Lógica de negocio
│   ├── templates/<app_name>/
│   └── tests.py
```

- Lógica de negocio en **`services/`**, no en vistas.
- Vistas delgadas: validar permisos → llamar servicio → renderizar o redirect.

### Servicios y mensajes al usuario

Reglas obligatorias al implementar `apps/<app>/services/` — detalle en [`UI_MESSAGES.md`](UI_MESSAGES.md) §9:

| Obligación | Resumen |
|------------|---------|
| Retorno estructurado | `ok`, `error_code`, `user_message`, `errors` (cuando aplique) |
| Textos | Solo catálogo §3; excepciones técnicas → `logger.exception` |
| Validación POST | `validation_form` + `errors` por campo; vista re-renderiza con `posted` |
| Éxito | Vista hace `messages.success` + redirect (PRG) |

---

## 3. Seguridad en vistas

Detalle completo en [`VISTAS.md`](VISTAS.md) (decoradores, tenant, POST sin Forms).

Toda vista bajo `/app/` requiere:

1. `@login_required` o decorador equivalente
2. `security_complete_required` — ver [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md)
3. `profile.company` asignado — sin compañía no hay acceso a negocio
4. Suscripción vigente para US/UF — ver [`billing.md`](billing.md)
5. Para recursos de proyecto: `project_permission_required` — ver [`projects.md`](projects.md)

### Aislamiento por compañía (tenant)

Patrón obligatorio en querysets de negocio:

```python
company = request.user.profile.company
Project.objects.filter(company=company, ...)
```

Ver [`company.md`](company.md) y [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md).

---

## 4. URLs

| Zona | Prefijo | Ejemplo |
|------|---------|---------|
| Pública / login | `/` | `/ingresar/` |
| Zona privada | `/app/` | `/app/proyectos/` |
| Admin usuarios | `/app/admin/usuarios/` | Solo UA/US |

---

## 5. Templates

- Zona privada `/app/`: extender `app_base.html` (shell, sidebar, modales).
- Páginas públicas: extender `base.html`.
- Nombre de archivo: `<app>_<accion>.html` — ver [`VISTAS.md`](VISTAS.md#103-templates-html)
- Usar `{% csrf_token %}` en formularios POST
- Mensajes flash vía `django.contrib.messages` → modal (`dw-modals.js`); validación de formulario inline
- Catálogo de textos y `error_code`: [`UI_MESSAGES.md`](UI_MESSAGES.md)
- Confirmaciones destructivas: `dwConfirmWarning()` — no `confirm()` nativo
- CSS app: `static/css/app.css` (workbench ledger)

### Cobertura de pantalla (layout `/app/`)

Esquema obligatorio para **nuevas pantallas** — detalle en [`VISTAS.md`](VISTAS.md#108-cobertura-de-pantalla-layout) §10.8.

| Tipo de pantalla | `{% block main_class %}` | Panel / tabla |
|------------------|--------------------------|---------------|
| Listado con DataTables | `app-main--wide` | `panel panel--table` + `table-dt-host` |
| Formulario CRUD (create/update) | (vacío — ancho estándar) | `panel` + `panel-body` |
| Detalle / confirmación | (vacío) | `panel` según diseño |

- **Listados:** usar todo el ancho útil (`app-main--wide`); no limitar a 1080px.
- **Tablas:** contenedor `table-dt-host`; scroll horizontal solo si el contenido desborda (`overflow-x: auto` en `app.css`).
- **Columna Acciones:** encabezado visible «Acciones»; botones en `.actions.actions--table` sin recorte (`panel--table` evita `overflow: hidden` en tablas).
- **Texto largo en celdas:** ellipsis en columnas secundarias (email, nombre) para priorizar acciones.
- **CSS por app:** estilos de tabla específicos en `static/css/<app>.css` (p. ej. `accounts.css`), no duplicar reglas globales de layout.

---

## 6. Correo

- Servicio central: `apps.core.services.email_delivery`
- **Desarrollo** (`DEBUG=True`): modo `console` forzado — códigos de verificación en la terminal del `runserver`; no usar Resend ni correos reales para pruebas locales.
- **Producción** (`DEBUG=False`): `EMAIL_DELIVERY=resend` + `RESEND_API_KEY`.

Ver [`core.md`](core.md) § Servicio de correo y [`../security/GUIA_IMPLEMENTACION_SEGURIDAD.md`](../security/GUIA_IMPLEMENTACION_SEGURIDAD.md) §5.3.

---

## 7. Documentos relacionados

- [`README.md`](README.md) — índice de apps
- [`UI_MESSAGES.md`](UI_MESSAGES.md) — mensajes UI, `error_code`, reglas servicio/vista
- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md) — modelos de datos
- [`VISTAS.md`](VISTAS.md) — reglas de vistas Python
- [`../DynamicWorkspace.md`](../DynamicWorkspace.md) — arquitectura general
