# apps.records

Registros de datos por proyecto (`Record`, `FieldValue`).

---

## Propósito

Almacenar y gestionar filas de datos según el esquema dinámico de cada proyecto (modelo híbrido).

---

## Responsabilidades

| Sí | No |
|----|-----|
| CRUD de `Record` y `FieldValue` | Definición de campos (→ `apps.fields`) |
| Listado paginado tipo Excel | Auditoría detallada (→ `apps.audit`) |
| Filtros y búsqueda | Importación (→ `apps.imports`) |
| Soft delete | Exportación (Fase 2) |

---

## Modelos

Detalle completo en [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md#record).

### Record

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `project` | FK Project | — |
| `created_by` | FK User | Autor |
| `updated_by` | FK User, null | Última modificación |
| `created_at` / `updated_at` | DateTimeField | — |
| `is_deleted` | BooleanField | Soft delete |

### FieldValue (modelo híbrido)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `record` | FK Record | — |
| `field` | FK FieldDefinition | — |
| `value_text` | TextField, null | Texto |
| `value_number` | DecimalField, null | Números |
| `value_date` | DateField, null | Fechas |
| `value_boolean` | BooleanField, null | Sí/No |
| `value_json` | JSONField, null | Tipos compuestos |

---

## Reglas

- Validar cada valor contra `FieldDefinition` del proyecto antes de guardar.
- Formularios HTML planos generados dinámicamente según campos del proyecto.
- Permisos: `edit` para crear/modificar; `view` para consulta.
- Listado con paginación; filtros por columnas tipadas.

---

## URLs previstas

| URL | Permiso |
|-----|---------|
| `/app/proyectos/<slug>/registros/` | `view` |
| `/app/proyectos/<slug>/registros/nuevo/` | `edit` |
| `/app/proyectos/<slug>/registros/<id>/` | `view` |
| `/app/proyectos/<slug>/registros/<id>/editar/` | `edit` |

---

## Prototipos HTML

Ubicación: `prototype/records/` · Estado: **en revisión** (OK pendiente).

| Archivo | URL de referencia | Rol ejemplo | Notas |
|---------|-------------------|-------------|-------|
| `record_list.html` | `/registros/` | ED | DataTables §10.8; columnas dinámicas (codigo, descripcion, cantidad, categoria, precio_unitario, Actualizado) |
| `record_create.html` | `/registros/nuevo/` | ED | Formulario dinámico; todos los tipos MVP del esquema inventario-2026 |
| `record_detail.html` | `/registros/<id>/` | CO | Solo lectura; metadatos Record + valores FieldValue |
| `record_update.html` | `/registros/<id>/editar/` | ED | Mismo formulario que crear, valores precargados |
| `record_expand.html` | `/registros/expandir/` | ED | Vista expandida; tema por proyecto (`ProjectRecordsExpandTheme`) |
| `record_expand_display.html` | `/registros/expandir/apariencia/` | PA | Configurar apariencia de tabla expandida |

Estáticos: `records.css`, `datatables-record.js`, `record-expand-display.js` (vista previa del formulario PA).

**Implementación:** modelo `ProjectRecordsExpandTheme` en `apps.projects`; servicio `apps/records/services/expand_display.py`; URL `/registros/expandir/apariencia/` (solo PA).

**Diseño tipo hoja de cálculo (DataTables):** ver [`records_datatables_design.md`](records_datatables_design.md) — características dinámicas por proyecto, modelo `ProjectRecordsExpandTheme`, roadmap visual.

**Producción:** create/update unificados en `templates/records/record_form.html` (ver [`VISTAS.md`](VISTAS.md)). Registrar URLs en `dynamicworkspace/urls.py` al mismo nivel que `fields`:

```python
path("app/proyectos/<slug:slug>/registros/", include(("apps.records.urls", "records"))),
```

Enlace desde `prototype/projects/project_detail.html` → `../records/record_list.html`.

---

## Dependencias

- `apps.projects` — permisos
- `apps.fields` — esquema y validación
- `apps.audit` — historial de cambios

## Fase

**Fase 1** — MVP.

## Documentos relacionados

- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md)
- [`fields.md`](fields.md)
- [`audit.md`](audit.md)
