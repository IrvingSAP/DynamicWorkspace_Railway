# Módulo 1c — Auditoría de clientes de máquina (PLATFORM API)

Trazabilidad **append-only** del ciclo de vida de `ApiClient` (alta, configuración, rotación, revelado, revocación).

> **Estado:** **implementado** (`ApiClientAuditEvent`, UI US)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §4 (identidad de máquina)  
> **No sustituye:** [`pa_audit.md`](pa_audit.md) (módulo 7: jobs `trigger_source=api`) ni [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §7.1

---

## Propósito

Un cambio de scopes, una rotación de key o una revocación **rompe o altera el ciclo de proceso** del ERP/RPA. Debe quedar evidencia de:

- **quién** (US)
- **cuándo**
- **qué acción**
- **antes / después** (configuración; nunca el secreto en claro)

---

## Acciones registradas

| Acción | Código | Cuándo |
|--------|--------|--------|
| Alta | `created` | `create_client` |
| Cambio de configuración | `updated` | Código, nombre, descripción o scopes (si hay diff) |
| Rotación de key | `key_rotated` | Nueva key; la anterior deja de autenticar |
| Key mostrada | `key_revealed` | US vio la bóveda de un solo uso |
| Revocación | `revoked` | Cliente inhabilitado |

No se registra cada `GET /api/v1/whoami`. El pulso de uso sigue en `ApiClient.last_used_at`.

No se persiste plaintext ni `secret_hash`. Sí `key_hint` para reconocer rotaciones.

Los eventos **no se editan ni se borran** desde la UI (admin Django: solo lectura).

---

## Tenancy y acceso

| Rol | Acceso |
|-----|--------|
| US de la compañía | Listado de la compañía, línea de tiempo por cliente, detalle de evento |
| UF / UA | Sin menú (UF: familia API deshabilitada) |
| Otra compañía | 404 lógico: el evento no existe para ese tenant |

---

## UI y URLs

| Ruta | Pantalla |
|------|----------|
| `/app/platform-api/auditoria/` | Todos los eventos de la compañía |
| `/app/platform-api/auditoria/<id>/` | Detalle antes/después |
| `/app/platform-api/clientes/<id>/auditoria/` | Timeline del cliente |

Sidebar US: **Auditoría API**. Desde listado y ficha: botón **Auditoría**.

---

## Relacionados

[`pa_auth.md`](pa_auth.md) · [`pa_audit.md`](pa_audit.md) · [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.17
