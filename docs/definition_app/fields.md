# apps.fields

Definición dinámica de campos por proyecto (`FieldDefinition`).

---

## Propósito

Permitir que cada proyecto defina su esquema (tipos, longitudes, validaciones) sin modificar código.

---

## Responsabilidades

| Sí | No |
|----|-----|
| CRUD de `FieldDefinition` | Almacenar valores (→ `apps.records`) |
| Validadores por tipo de campo | Permisos de proyecto (→ `apps.projects`) |
| Orden de campos (`sort_order`) | Importación Excel (→ `apps.imports`) |

---

## Modelo FieldDefinition

Detalle completo en [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md#fielddefinition).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `project` | FK Project | Proyecto dueño |
| `key` | SlugField | Identificador interno |
| `label` | CharField | Etiqueta visible |
| `field_type` | CharField | text, number, date, boolean, select, etc. |
| `options` | JSONField | Opciones (listas, rangos) |
| `max_length` | IntegerField, null | Longitud máxima |
| `required` | BooleanField | Obligatorio |
| `sort_order` | IntegerField | Orden en UI |
| `version` | IntegerField | Versionado de esquema |

---

## Tipos de campo — MVP

| Tipo | Validaciones |
|------|--------------|
| `text_short` | Longitud máxima |
| `text_long` | Longitud máxima |
| `integer` | Rango min/max |
| `decimal` | Rango, decimales |
| `date` | Formato, rango |
| `datetime` | Formato, rango |
| `boolean` | Sí/No |
| `select` | Opciones en `options` |

---

## Reglas

- Solo rol `PA` puede crear/editar/eliminar campos.
- Cambio de tipo requiere validación de migración de datos existentes.
- Validación en servicio `fields/services/validators.py` — un validador por tipo.

---

## URLs previstas

| URL | Permiso |
|-----|---------|
| `/app/proyectos/<slug>/campos/` | `design` |
| `/app/proyectos/<slug>/campos/nuevo/` | `design` |

---

## Prototipos HTML

Carpeta: `prototype/fields/` · Design system: **workbench ledger** (extiende `dashboard.css`).

| Prototipo | URL prevista | Layout | Descripción |
|-----------|--------------|--------|-------------|
| `field_list.html` | `/app/proyectos/<slug>/campos/` | Listado §10.8 | Diseñador de campos (PA) |
| `field_create.html` | `/app/proyectos/<slug>/campos/nuevo/` | Formulario | Alta de `FieldDefinition` |

### Layout

Alineado con [`VISTAS.md`](VISTAS.md#108-cobertura-de-pantalla-layout) §10.8 — misma referencia que `prototype/projects/`.

| Regla | Prototipo |
|-------|-----------|
| `app-main--wide` | Solo `field_list.html` |
| `panel panel--table` + `table-dt-host--fields` | Listado DataTables |
| Formulario | `app-main` estándar en `field_create.html` |
| Alcance | Franja `project-scope-strip` con slug del proyecto |

**Assets:** `fields.css`, `datatables-field.js`, `field-form.js` (paneles condicionales por tipo).

**Navegación:** enlazado desde `prototype/projects/project_detail.html` (tarjeta Campos). Sidebar UF: Proyectos.

Tras el OK: migrar a `templates/fields/`; eliminar archivos de `prototype/fields/`.

---

## Dependencias

- `apps.projects` — proyecto y permisos

## Fase

**Fase 1** — MVP.

## Documentos relacionados

- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md)
- [`projects.md`](projects.md)
- [`records.md`](records.md)
