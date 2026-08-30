# Módulo 1 — Autenticación y tenancy (PLATFORM API)

Identidad de máquina, scopes y aislamiento por `Company`.

> **Estado:** **implementado** (`apps.platform_api` — clientes, hash, rotar/revocar, auditoría de ciclo de vida, Bearer `/api/v1/whoami`)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §4 · §4.1  
> **Fase:** A (obligatorio antes de producción)  
> **Prototipo:** [`../../prototype/platform_api/`](../../prototype/platform_api/) (`api_clients`, create, reveal, detail)

---

## Propósito

Permitir que un **cliente de máquina** (ERP, RPA, middleware) invoque `/api/v1/…` ligado a **una** `Company`, con scopes explícitos. No sustituye login UF + 2FA ([`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md)).

---

## Alcance

| Sí | No |
|----|-----|
| API key y/o OAuth2 client-credentials (decidir en implementación; ambos → `Company`) | Registro público de integradores |
| Scopes por acción | Token “dios” de toda la compañía |
| Rotación / revocación / keys por entorno (sandbox ≠ prod) | Inventar roles PA/ED/GE/CO nuevos |
| Comprobar compañía activa + paquete / feature flag | Autorizar proyectos ajenos o cross-tenant |

---

## Scopes (mínimo)

| Scope | Permite | Módulo |
|-------|---------|--------|
| `jobs:run` | `POST /jobs/run` (kind suelto) | [`pa_jobs_run.md`](pa_jobs_run.md) |
| `pipeline:run` | Cadena publicada | [`pa_pipeline.md`](pa_pipeline.md) |
| `jobs:read` | GET job / listado | [`pa_jobs_query.md`](pa_jobs_query.md) |
| `jobs:cancel` | Cancelar en curso | [`pa_jobs_ops.md`](pa_jobs_ops.md) |
| `artifacts:download` | Informe / archivo | [`pa_jobs_query.md`](pa_jobs_query.md) |

El scope de máquina **no** es más permisivo que el rol UI equivalente (p. ej. sin bytes de artifact si CO no descarga).

Ejecutar un proyecto exige derecho equivalente a **GE** (o servicio) sobre ese proyecto. Pipeline: permiso en **todos** los pasos o se deniega el run — [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §6.

---

## Modelo conceptual (borrador)

```text
Company
  └── ApiClient (código, nombre, descripción, entorno, activo, created_by)
        ├── hashed secret / OAuth client
        ├── scopes[]
        └── (opcional) allowlist de project_id / pipeline_id
        └── ApiClientAuditEvent[] (append-only: alta, update, rotar, revelar, revocar)
```

Secretos: guardar **hash**, no el valor en claro. Mostrar la key **una vez** al crear (o al rotar).

### Ciclo de vida de la key (importante)

Un `ApiClient` = una identidad de máquina **estable**. La key **no** se emite por cada llamada ni por cada job.

| Momento | ¿Nueva key? | Qué ocurre |
|---------|-------------|------------|
| Alta del cliente | **Sí** (una vez) | Reveal: Ana la copia al vault del banco y cierra. DW no la vuelve a mostrar. |
| Cada `POST /jobs/run` (lunes, martes, 06:00…) | **No** | El ERP reenvía el **mismo** Bearer. La configuración (scopes, compañía, entorno) ya está asociada a ese cliente. |
| Cambiar scopes, nombre, allowlist | **No** | Se edita el cliente; el secreto sigue válido. |
| Compromiso, caducidad o política de rotación | **Sí** (rotar) | Se emite otra key (otro reveal). La anterior deja de autenticar. Jobs **pasados** no se rehacen. |
| Baja del integrador | **No** | **Revocar** el cliente: todas las keys de ese cliente dejan de servir. |

Rotar ≠ crear un cliente nuevo (salvo que se quiera otra identidad / otro entorno / otros scopes de raíz). Sandbox y prod son **clientes distintos**, cada uno con su key.

UI de alta de clientes: fase posterior (US/PA de compañía); **no** es sidebar de archivo. Este módulo define el contrato; pantallas HTML solo si se pide prototipo.

---

## HTTP (visión)

| Caso | Código |
|------|--------|
| Sin token / token inválido | 401 |
| Compañía inactiva / sin flag | 403 |
| Scope insuficiente | 403 |
| Recurso de otra `Company` | 404 o 403 (no filtrar existencia cross-tenant) |

Header: `Authorization: Bearer <token>`.

---

## Criterio de aceptación (diseño)

1. ¿Toda llamada autenticada queda ligada a una `Company`?  
2. ¿Scopes granulares documentados (no un único `admin`)?  
3. ¿Rotación y revocación previstas?  
4. ¿Sin producción sin este módulo?

---

## Relacionados

[`pa_security.md`](pa_security.md) · [`pa_integration.md`](pa_integration.md) · [`pa_client_audit.md`](pa_client_audit.md) · [`../PLATFORM_API.md`](../PLATFORM_API.md) §4
