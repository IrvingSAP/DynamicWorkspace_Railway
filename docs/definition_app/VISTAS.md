# Reglas globales — vistas Python (Django)

Reglas obligatorias al crear o modificar vistas en `apps/*/views.py`. Complementa [`CONVENCIONES.md`](CONVENCIONES.md).

**Relacionados:** seguridad [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md) · tenant [`company.md`](company.md) · permisos proyecto [`projects.md`](projects.md) · modelos [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md) · **mensajes UI** [`UI_MESSAGES.md`](UI_MESSAGES.md)

---

## 1. Principio: vistas delgadas

Una vista solo debe:

1. Verificar autenticación y permisos
2. Leer `request.GET` / `request.POST`
3. Delegar lógica a un **servicio** (`apps/<app>/services/`)
4. Devolver `render()`, `redirect()` o `HttpResponse`

| Sí en la vista | No en la vista |
|----------------|----------------|
| Decoradores de acceso | Reglas de negocio complejas |
| Extraer parámetros de URL/body | Consultas ORM extensas |
| Llamar al servicio | Validación de dominio repetida |
| Elegir plantilla y contexto | Envío de correo, TOTP, billing |
| Mensajes flash (`messages`) | Cálculos sobre registros/campos |
| Aplicar catálogo UI | Textos libres o `str(exception)` al usuario |

> Mensajes y errores: reglas obligatorias en [`UI_MESSAGES.md`](UI_MESSAGES.md). La vista elige canal (modal vs inline); el servicio provee `error_code` y textos.

---

## 2. Estructura de archivo

```
apps/<app>/
├── views.py              # o views/ si crece
├── services/
│   ├── __init__.py
│   └── <dominio>.py      # p. ej. project_list.py, record_save.py
├── urls.py
└── templates/<app>/
```

- Una vista = una responsabilidad HTTP clara (listar, crear, editar, eliminar).
- Si `views.py` supera ~200 líneas, dividir en `views/` por dominio.

---

## 3. Zonas y decoradores

### 3.1 Vista pública (login, seguridad)

Rutas fuera de `/app/`: `apps.security`, landing.

| Requisito | Detalle |
|-----------|---------|
| Autenticación | No exigir `@login_required` en login/TOTP |
| CSRF | `@csrf_protect` en POST (por defecto en Django) |
| Sesión wizard | Usar `security_pending_user_id`; ver [`security.md`](security.md) |

### 3.2 Vista privada (`/app/`)

Cadena mínima de decoradores (de afuera hacia adentro):

```python
@login_required
@security_complete_required
def dashboard_home(request):
    ...
```

| Decorador | Cuándo |
|-----------|--------|
| `@login_required` | Toda vista `/app/` |
| `@security_complete_required` | Tras login; exige correo + 2FA completos |
| `@company_required` | Negocio: exige `request.user.profile.company` |
| `@subscription_required` | US/UF: suscripción vigente (UA exento) |
| `@user_type_required("UA", "US")` | Paneles admin (usuarios, compañías) |
| `@project_permission_required("edit")` | Recursos de un proyecto |

> Implementación de decoradores en `apps/core/decorators.py`.

### 3.3 Vista de proyecto

```python
@login_required
@security_complete_required
@company_required
@subscription_required
@project_permission_required("view")
def project_detail(request, project_slug):
    project = get_project_for_user(request.user, project_slug)
    ...
```

Orden: **auth → seguridad → compañía → suscripción → permiso de proyecto**.

---

## 4. Aislamiento por compañía (tenant)

**Regla:** todo queryset de negocio filtra por la compañía del usuario conectado.

```python
def get_company(request):
    return request.user.profile.company

def projects_queryset(user):
    company = user.profile.company
    return Project.objects.filter(company=company, is_archived=False)
```

| Situación | Acción |
|-----------|--------|
| Usuario sin `profile.company` | Redirect o 403; queryset vacío |
| Objeto de otra compañía | `get_object_or_404` con filtro `company=...` |
| UA cross-tenant | Solo si la vista lo permite explícitamente (soporte) |
| Alta de usuario por US | Forzar `company = request.user.profile.company` |
| CRUD usuarios (`apps.accounts`) | UA solo gestiona **US**; US solo gestiona **UF** de su compañía — ver [`accounts.md`](accounts.md) § List y CRUD |
| Aprovisionamiento masivo UF | Pendiente Fase 1+ — [`accounts_provisioning.md`](accounts_provisioning.md) |

Nunca confiar en IDs de URL sin validar que el recurso pertenece a la compañía del usuario.

---

## 5. Sin Django Forms

Prohibido: `forms.py`, `ModelForm`, `form.is_valid()`.

### GET — mostrar formulario

```python
def record_create(request, project_slug):
    project = get_project_for_user(request.user, project_slug, permission="edit")
    fields = get_active_fields(project)
    return render(request, "records/record_form.html", {
        "project": project,
        "fields": fields,
    })
```

### POST — procesar formulario HTML

```python
def record_create(request, project_slug):
    if request.method != "POST":
        return redirect("records:create", project_slug=project_slug)

    project = get_project_for_user(request.user, project_slug, permission="edit")
    result = record_service.create_from_post(project, request.user, request.POST)

    if result.errors:
        return render(request, "records/record_form.html", {
            "project": project,
            "fields": result.fields,
            "errors": result.errors,
            "posted": request.POST,
        })

    messages.success(request, "Registro creado.")
    return redirect("records:detail", project_slug=project_slug, record_id=result.record.id)
```

- Validación en **servicio** (`record_service`, `validators/`).
- Repoblar valores con `posted` en caso de error.
- Siempre `{% csrf_token %}` en el template.

---

## 6. Servicios

Cada operación de negocio expone funciones en `services/`:

```python
# apps/records/services/record_save.py
def create_from_post(project, user, post_data) -> SaveResult:
    errors = validate_record(project, post_data)
    if errors:
        return SaveResult(ok=False, errors=errors, fields=get_active_fields(project))
    record = persist_record(project, user, post_data)
    audit_service.log_create(record, user)
    return SaveResult(ok=True, record=record)
```

La vista **no** llama a `Record.objects.create()` directamente salvo casos triviales acordados.

---

## 7. Querysets y `get_object_or_404`

```python
# Correcto — scoped por compañía
project = get_object_or_404(
    Project,
    slug=project_slug,
    company=request.user.profile.company,
)

# Incorrecto — ID sin tenant
project = get_object_or_404(Project, pk=project_id)
```

- Preferir funciones helper: `get_project_for_user()`, `get_record_for_user()`.
- Paginación: `Paginator` en servicio o vista; nunca cargar todos los registros.

---

## 8. Respuestas HTTP y mensajes

Reglas obligatorias — detalle y catálogo de textos en [`UI_MESSAGES.md`](UI_MESSAGES.md).

| Caso | Respuesta | Canal UI |
|------|-----------|----------|
| Éxito crear/editar/eliminar | `redirect` + `messages.success` | Modal (PRG) |
| Error de validación POST | `render` mismo template con `errors` + `posted` | Inline en campos |
| Error de negocio / persistencia | `render` o `redirect` + `messages.error` | Modal; texto §3 |
| Aviso operativo | `messages.warning` | Modal |
| Información (sin fallo) | `messages.info` | Modal |
| Sin permiso | `raise PermissionDenied` o redirect + `messages.error` | §3.4 |
| Recurso inexistente / otro tenant | `Http404` o `messages.error` según flujo | §3.2 |
| POST inválido (método) | `redirect` o `405` según convención de la app | — |
| Confirmar eliminación | `dwConfirmWarning` en template → POST | §3.3 (no `confirm()`) |

Evitar `print()`; usar logging (`logger = logging.getLogger(__name__)`). **Nunca** exponer `str(exception)` al usuario (ver `UI_MESSAGES.md` §4).

---

## 9. Contexto de template

Convención de nombres en el dict de contexto:

| Clave | Uso |
|-------|-----|
| `project` | Proyecto actual (vistas de proyecto) |
| `company` | Compañía del usuario (si aplica) |
| `fields` | Definiciones de campo para formularios dinámicos |
| `records` / `items` | Listados paginados |
| `errors` | Dict campo → lista de mensajes (`UI_MESSAGES.md` §1) |
| `posted` | Datos enviados para repoblar el formulario |

No pasar el queryset completo sin paginar en listados grandes.

---

## 10. Naming — prefijo de app obligatorio

**Regla:** toda función de vista y todo template HTML llevan el **nombre de la app** como prefijo, seguido de la acción que cumple. Facilita identificar origen y responsabilidad en `views.py`, `urls.py` y el árbol de plantillas.

### 10.1 Funciones de vista

Formato: `<app>_<accion>` en `snake_case`.

| Acción | Sufijo | Función |
|--------|--------|---------|
| Listado | `_list` | `company_list` |
| Crear | `_create` | `company_create` |
| Detalle | `_detail` | `company_detail` |
| Editar | `_update` | `company_update` |
| Eliminar | `_delete` | `company_delete` |
| Confirmar borrado | `_confirm_delete` | `company_confirm_delete` |

Otras apps siguen el mismo patrón: `project_list`, `record_create`, `account_update`, etc.

### 10.2 URLs (`urls.py`)

El `name` de la URL es corto (acción); la **vista** siempre con prefijo de app:

```python
# apps/company/urls.py
from django.urls import path

from apps.company import views

app_name = "company"

urlpatterns = [
    path("", views.company_list, name="list"),
    path("nueva/", views.company_create, name="create"),
    path("<int:pk>/", views.company_detail, name="detail"),
    path("<int:pk>/editar/", views.company_update, name="update"),
    path("<int:pk>/eliminar/", views.company_delete, name="delete"),
]
```

Uso en templates y redirects: `{% url 'company:list' %}`, `redirect("company:detail", pk=obj.pk)`.

### 10.3 Templates HTML

Formato: `<app>_<accion>.html` dentro de `templates/<app>/`.

| Vista | Archivo template |
|-------|------------------|
| `company_list` | `templates/company/company_list.html` |
| `company_create` | `templates/company/company_form.html` o `company_create.html` |
| `company_detail` | `templates/company/company_detail.html` |
| `company_update` | `templates/company/company_form.html` o `company_update.html` |
| `company_delete` | `templates/company/company_confirm_delete.html` |

Ejemplos válidos:

- `company_list.html`
- `company_detail.html`
- `company_confirm_delete.html`
- `project_list.html`
- `record_create.html`

En la vista:

```python
return render(request, "company/company_list.html", context)
```

### 10.4 Resumen

| Elemento | Convención | Ejemplo |
|----------|------------|---------|
| Función vista | `<app>_<accion>` | `company_list`, `company_create` |
| URL `name` | `<accion>` (con `app_name`) | `company:list`, `company:create` |
| Template | `<app>/<app>_<accion>.html` | `company/company_list.html` |
| Servicio | módulo o función por dominio | `company_service.py`, `list_companies()` |

**Prohibido** nombres genéricos sin prefijo en vistas: `list`, `create`, `detail`, `update`, `delete`.

### 10.5 Prototipos HTML (previo a implementación)

Antes de crear la plantilla en `templates/`, diseñar y validar en `prototype/<app>/`.

| Fase | Ubicación |
|------|-----------|
| Prototipo (revisión) | `prototype/company/company_list.html` · `prototype/projects/project_list.html` |
| Producción (tras OK) | `templates/company/company_list.html` |

Flujo completo: [`PROTOTIPOS.md`](PROTOTIPOS.md) · [`../../prototype/README.md`](../../prototype/README.md)

1. Crear HTML en `prototype/<app>/` con el **mismo nombre** que la plantilla final.
2. Revisar UX, campos y reglas.
3. Tras OK → implementar en `templates/<app>/` + vista Python.
4. **Eliminar** el archivo de `prototype/<app>/`.

### 10.6 Tablas HTML — DataTables

**Regla:** toda tabla de datos en HTML (prototipos y plantillas) se implementa con [DataTables](https://datatables.net/manual/).

| Requisito | Detalle |
|-----------|---------|
| Librería | [DataTables](https://datatables.net/manual/) + **jQuery 3.x** (dependencia obligatoria) |
| Marcado | `<table id="<app>-table" class="dw-datatable">` con `<thead>` / `<tbody>` |
| Paginación | `pageLength: 10`, `lengthMenu: [10, 25, 50]` |
| Búsqueda | Campo global de DataTables (`dom` incluye `f`) |
| Ordenar | Cabeceras ordenables en columnas definidas por app + selector en toolbar si aplica |
| Filtrar | Controles en `.table-toolbar` según columnas filtrables de la vista |
| Inicialización | `static/js/datatables-init.js` en producción; CDN + script en prototipos |
| Idioma | Español (`es-ES`) vía plug-in i18n de DataTables |
| Columna acciones | Última columna: `orderable: false`, `searchable: false` |
| Estilos | Overrides en CSS del módulo para integrar con el design system |

**Controles mínimos por tabla de listado:**

| Control | Implementación |
|---------|----------------|
| Paginación | `lengthMenu: [10, 25, 50]` |
| Búsqueda | Filtro global DataTables |
| Ordenar | Click en `<th>` o `<select id="sort-by">` en toolbar |
| Filtrar | `<select>` / inputs en `.table-toolbar` + `DataTable.ext.search` o `column().search()` |

**Filtros por app (company):**

| Filtro | Columna / atributo |
|--------|-------------------|
| Estado | `data-estado` en `<tr>` + `#filter-estado` (activa / inactiva) |
| Ordenar | Código (col 0), Organización (col 1) |

**Prototipo (CDN):**

```html
<link rel="stylesheet" href="https://cdn.datatables.net/2.2.2/css/dataTables.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/2.2.2/js/dataTables.min.js"></script>
```

> DataTables 2 **requiere jQuery** antes de su script. Sin jQuery, `DataTable` queda `undefined` y no aparecen búsqueda ni paginación.

**Producción (`base.html` o bloque `scripts`):**

```html
{% load static %}
<link rel="stylesheet" href="https://cdn.datatables.net/2.2.2/css/dataTables.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/2.2.2/js/dataTables.min.js"></script>
<script src="{% static 'js/datatables-init.js' %}"></script>
```

```javascript
// static/js/datatables-init.js
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.dw-datatable').forEach((table) => {
    if (table.dataset.dtInit === 'true') return;
    new DataTable(table, {
      language: { url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-ES.json' },
      pageLength: 10,
      lengthMenu: [10, 25, 50],
      dom: '<"dt-top"lf>rt<"dt-bottom"ip>',
      order: defaultOrder,
      columnDefs: [{ orderable: false, searchable: false, targets: -1 }],
    });
    table.dataset.dtInit = 'true';
  });
});
```

**No usar** tablas HTML estáticas sin DataTables en vistas de listado. Tablas de solo lectura en detalle (pocos campos) pueden ser markup simple si no requieren búsqueda ni paginación.

### 10.7 Layout privado y modales (`app_base.html`)

Zona `/app/`: todas las plantillas extienden `templates/app_base.html` (workbench ledger en `static/css/app.css`).

| Bloque | Uso |
|--------|-----|
| `{% block title %}` | `<title>` del documento |
| `{% block main_class %}` | Clases extra en `<main>` — listados: `app-main--wide` |
| `{% block extra_css %}` | CSS por vista (p. ej. DataTables CDN) |
| `{% block sidebar_nav %}` | Menú lateral; por defecto `includes/sidebar_ua.html` |
| `{% block sidebar_extra %}` | Subsección opcional (p. ej. Billing) |
| `{% block breadcrumb %}` | Migas de pan |
| `{% block content %}` | Contenido principal |
| `{% block extra_js %}` | Scripts por vista |

**Mensajes flash** (`django.contrib.messages`):

| Caso | Mecanismo |
|------|-----------|
| Éxito tras POST (PRG) | `messages.success` → modal verde al cargar destino |
| Error de negocio / permiso | `messages.error` → modal rojo |
| Aviso operativo | `messages.warning` → modal ámbar |
| Información | `messages.info` → modal informativo |
| Validación de formulario | `render` + `errors` en contexto → **inline** en campos, no modal |

`app_base.html` serializa los mensajes en `#dw-flash-messages` (JSON). `static/js/dw-modals.js` los encola y muestra uno tras otro.

**Confirmación destructiva** (eliminar, revocar):

```javascript
dwConfirmWarning('¿Eliminar este registro?', function () {
    form.submit();
}, { title: 'Confirmar eliminación', okLabel: 'Eliminar' });
```

Atributo en listados: `data-dw-delete` + `data-dw-delete-message` (ver `datatables-company.js`).

**API adicional:** `dwShowMessage('error', 'Texto')` para mensajes desde JS sin round-trip.

**Contexto de navegación:** `app_nav_active` — valores: `home`, `company`, `accounts`, `billing`, `projects`, etc.

Catálogo completo de textos, `error_code` y flujo vista↔servicio: [`UI_MESSAGES.md`](UI_MESSAGES.md).

### 10.8 Cobertura de pantalla (layout)

Reglas de **ancho y tablas** para la zona privada. Referencia implementada: `company_list.html`, `accounts/account_list.html`. Prototipo alineado: `prototype/projects/project_list.html`.

#### Principios

1. **Listados administrativos** ocupan el ancho disponible del área principal (sidebar + contenido fluido).
2. **Formularios y detalle** mantienen lectura cómoda sin forzar ancho completo (sin `app-main--wide`).
3. **Nunca recortar** columnas de acción: si la tabla no cabe, scroll horizontal en `table-dt-host`, no `overflow: hidden` en el panel.

#### Clases y bloques (`app_base.html`)

```django
{% extends "app_base.html" %}

{% block main_class %}app-main--wide{% endblock %}  {# solo listados con tabla #}
```

| Clase | CSS (`app.css`) | Cuándo |
|-------|-----------------|--------|
| `app-main` | `flex: 1; width: 100%` | Siempre (base) |
| `app-main--wide` | Sin `max-width` | Listados DataTables |
| `panel--table` | `overflow: visible` | Panel que envuelve una tabla |
| `table-dt-host` | `overflow-x: auto` | Contenedor directo de `<table>` |

#### Estructura HTML — listado

```html
<div class="panel panel--table">
    <div class="table-toolbar">…filtros…</div>
    <div class="table-dt-host table-dt-host--{app}" aria-label="…">
        <table id="{app}-table" class="dw-datatable">…</table>
    </div>
</div>
```

- Encabezado de última columna: **Acciones** (no dejar `<th>` vacío).
- Acciones: `<div class="actions actions--table">` con enlaces `btn btn-ghost btn-sm`.
- Eliminar: `data-dw-delete` + formulario inline (ver §10.6).

#### Columnas y responsive

| Regla | Detalle |
|-------|---------|
| Tabla | `width: 100%` en escritorio |
| Texto largo | `.td-email`, `.td-name` con `text-overflow: ellipsis` en CSS de la app |
| Columna acciones | `white-space: nowrap`, `width: 1%` |
| Viewport estrecho | `@media (max-width: 1100px)`: `min-width` en tabla + scroll en `table-dt-host` |

No fijar `min-width` global en la tabla en pantallas amplias (evita barra lateral innecesaria).

#### CSS por app

- Layout global: `static/css/app.css`
- Ajustes de tabla/columnas: `static/css/<app>.css` (importar en `{% block extra_css %}` del listado)
- Init DataTables: `static/js/datatables-<app>.js` + `datatables-init.js`

#### Checklist layout (nueva pantalla listado)

- [ ] `{% block main_class %}app-main--wide{% endblock %}`
- [ ] `panel panel--table` + `table-dt-host`
- [ ] Columna **Acciones** con todos los botones visibles en pantalla completa
- [ ] Scroll horizontal solo al reducir viewport (probar ~1920px y ~900px)
- [ ] Sin espacio vacío excesivo a la derecha en monitor ancho

---

## 11. Checklist al crear una vista

- [ ] ¿Está en la zona correcta (`/` vs `/app/`)?
- [ ] ¿Lleva los decoradores necesarios?
- [ ] ¿Filtra por `profile.company`?
- [ ] ¿Valida permiso de proyecto si aplica?
- [ ] ¿POST delegado a servicio sin Django Forms?
- [ ] ¿Servicio retorna `ok` / `error_code` / `errors` según [`UI_MESSAGES.md`](UI_MESSAGES.md) §9?
- [ ] ¿Listado DataTables? → `main_class` = `app-main--wide`, `panel--table`, `table-dt-host` (ver §10.8)
- [ ] ¿Éxito: `messages.success` con texto de §3 + redirect PRG?
- [ ] ¿Validación: `errors` inline (sin depender solo del modal)?
- [ ] ¿Errores de negocio: `messages.*` con texto del catálogo, no `str(e)`?
- [ ] ¿Eliminar: `dwConfirmWarning` antes del POST?
- [ ] ¿Función vista con prefijo de app (`company_list`, no `list`)?
- [ ] ¿Template con prefijo de app (`company/company_list.html`)?
- [ ] ¿Tablas de listado con DataTables (`dw-datatable`, paginación 10/25/50, búsqueda, filtros)?

---

## 12. Ejemplo completo (referencia)

```python
# apps/company/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import security_complete_required, user_type_required
from apps.company.services import company_service


@login_required
@security_complete_required
@user_type_required("UA")
def company_list(request):
    companies = company_service.list_all()
    return render(request, "company/company_list.html", {"companies": companies})


@login_required
@security_complete_required
@user_type_required("UA")
def company_create(request):
    if request.method == "POST":
        result = company_service.create_from_post(request.user, request.POST)
        if result.ok:
            # Texto: UI_MESSAGES.md §3.5
            messages.success(request, "Compañía creada correctamente.")
            return redirect("company:detail", pk=result.company.pk)
        if result.error_code == "validation_form":
            return render(request, "company/company_create.html", {
                "errors": result.errors,
                "posted": request.POST,
            })
        messages.error(request, result.user_message)  # catálogo §3
        return render(request, "company/company_create.html", {"posted": request.POST})
    return render(request, "company/company_create.html")


@login_required
@security_complete_required
@user_type_required("UA")
def company_detail(request, pk):
    company = get_object_or_404(company_service.queryset(), pk=pk)
    return render(request, "company/company_detail.html", {"company": company})
```

```python
# apps/company/urls.py — ver sección 10.2
urlpatterns = [
    path("", views.company_list, name="list"),
    path("nueva/", views.company_create, name="create"),
    path("<int:pk>/", views.company_detail, name="detail"),
    path("<int:pk>/editar/", views.company_update, name="update"),
    path("<int:pk>/eliminar/", views.company_delete, name="delete"),
]
```

---

## 13. Documentos relacionados

| Documento | Contenido |
|-----------|-----------|
| [`CONVENCIONES.md`](CONVENCIONES.md) | Resumen transversal |
| [`UI_MESSAGES.md`](UI_MESSAGES.md) | Catálogo de mensajes, `error_code`, reglas servicio |
| [`company.md`](company.md) | Tenant y compañía |
| [`billing.md`](billing.md) | Suscripción en acceso |
| [`projects.md`](projects.md) | Permisos por proyecto |
| [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md) | Login y 2FA |
| [`PROTOTIPOS.md`](PROTOTIPOS.md) | Flujo de prototipos HTML |
| [`.cursor/rules/django-conventions.mdc`](../../.cursor/rules/django-conventions.mdc) | Reglas Cursor (Forms, stack) |
| [`.cursor/rules/ui-messages.mdc`](../../.cursor/rules/ui-messages.mdc) | Reglas Cursor (mensajes UI) |

---

## Mantenimiento

Al añadir un decorador, patrón de permiso o convención nueva → actualizar **este archivo** y, si aplica, `apps/core/decorators.py` y `.cursor/rules/`.

---

*Reglas globales de vistas — `docs/definition_app/VISTAS.md`*
