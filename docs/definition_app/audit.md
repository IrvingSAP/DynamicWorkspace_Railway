# apps.audit

Auditoría e historial de cambios en registros.

---

## Propósito

Responder *¿quién creó/modificó este registro y cuándo?* y *¿quién cambió este valor?*

---

## Responsabilidades

| Sí | No |
|----|-----|
| `RecordHistory` por cambio de campo | Login / 2FA |
| Metadatos: usuario, fecha, valor anterior | UI de registros (→ `apps.records`) |
| Consulta de historial por registro | Permisos globales |

---

## Modelo RecordHistory

Detalle completo en [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md#recordhistory).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `record` | FK Record | Registro afectado |
| `field` | FK FieldDefinition, null | Campo (null = registro completo) |
| `user` | FK User | Quién hizo el cambio |
| `action` | CharField | create, update, delete |
| `old_value` | TextField, null | Valor anterior |
| `new_value` | TextField, null | Valor nuevo |
| `created_at` | DateTimeField | Cuándo |

---

## Reglas

- Escribir historial en servicio de `apps.records` al crear/actualizar/eliminar.
- Solo rol `PA` ve auditoría completa del proyecto (configurable en fases posteriores).
- No modificar ni eliminar entradas de historial.

---

## URLs previstas

| URL | Permiso |
|-----|---------|
| `/app/proyectos/<slug>/registros/<id>/historial/` | `audit` |

---

## Dependencias

- `apps.records`
- `apps.projects`

## Fase

**Fase 1** — auditoría básica en MVP; historial por campo en Fase 2.

## Documentos relacionados

- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md)
- [`records.md`](records.md)
- [`../DynamicWorkspace.md`](../DynamicWorkspace.md)
