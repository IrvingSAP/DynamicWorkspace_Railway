# PLATFORM API — Ejecución remota de jobs

> **Nombre mnemotécnico:** `PLATFORM_API`  
> Alias: *API de jobs* · *API de integración* · *Ejecución remota*  
> Archivo: [`docs/PLATFORM_API.md`](PLATFORM_API.md)  
> Estado: **implementado** (`apps.platform_api`) — consola US `/app/platform-api/` · HTTP `/api/v1/…`  
> Specs por módulo: [`definition_app_PLATFORM_API/`](definition_app_PLATFORM_API/) (M1–M9 en código). Manual de jobs sueltos: [`MANUAL_USUARIO_API_APP.md`](definition_app_PLATFORM_API/MANUAL_USUARIO_API_APP.md)  
> Padres: [`APP_FACTORY.md`](APP_FACTORY.md) §2.3 · [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) (disparadores)  
> Alcance: **todas las apps ejecutables** vía Job (Gate, Pipe, Reverse, Match, Scout, Clean, Split/Merge) y **File Pipeline** (`kind=file_pipeline`)  
> No cableados aún: Repair, Profiler (catálogo; `mvp_phase_a: false`)

---

## 0. Para qué sirve este documento

### Qué es

Documento de **plataforma** (no un vertical de menú) que define cómo sistemas externos invocan DynamicWorkspace por HTTP: envían identidad + qué app/proyecto + archivo(s) y reciben estado, errores tipados y, si aplica, archivo o informe.

### Qué función cumple

| Función | Descripción |
|---------|-------------|
| **Congelar la decisión** | Habrá una API de ejecución alineada a todas las apps con Job |
| **Delimitar** | API ≠ app de producto; no redefine contratos en cada request (MVP) |
| **Unificar contrato** | Entradas/salidas comunes + variaciones por `kind` |
| **Preparar implementación** | Fases A/B/C; auth, sync/async, webhooks, límites |

### Alcance (sí / no)

| Sí | No |
|----|-----|
| Ejecutar **versión publicada** de un proyecto existente | Sustituir la UI de diseño de esquemas/mapeos |
| Cubrir **todos los kinds ejecutables** con el mismo patrón | Un endpoint distinto “de producto” por app sin contrato común |
| Auth de máquina, scopes, idempotencia, informe, descarga, cancelar, consultar | CRUD de proyectos/miembros/billing vía API en MVP |
| Relación con Watch / Scheduler / Archive / Pipeline / tablero UI | Spec OpenAPI 3 YAML ni SDKs (sí índice `GET /api/v1/openapi`) |
| Auditoría de **ejecución** (job / pipeline run) visible en UI y por GET | API de métricas que sustituya el dashboard humano |
| `mode=pipeline` delegando al orquestador | Rediseñar pasos, publicar pipelines o editar esquemas por HTTP |

### En una frase

**La UI diseña y publica; la API ejecuta el mismo Job que un usuario GE haría a mano.**

---

## 1. Resumen ejecutivo

### Problema

Hoy la ejecución es **manual** (login → app → subir → ejecutar). ERPs, RPA, bancos y bots necesitan el mismo resultado **sin operador**: validar, transformar, emitir, conciliar o explorar de forma repetible y auditable.

### Solución

Capa HTTP de **ejecución de jobs**:

```text
Cliente (ERP / bot / middleware)
        ↓
  PLATFORM API  (auth + kind + proyecto + archivo[s])
        ↓
  Motor de la app (Gate / Pipe / Reverse / Match / Scout / …)
        ↓
  Respuesta: OK | errores | archivo(s) / informe + job_id
```

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Beneficio** | Integración sin reescribir el núcleo; misma auditoría que la UI |
| **Audiencia** | Integradores, IT, operaciones automatizadas, partners |
| **Diferenciador** | Un contrato de Job para **toda la suite**, no un API aislado por silo |
| **Reuso** | 100 % de parsers, reglas, versiones publicadas e historiales existentes |

### Principios de diseño

1. **Misma semántica que la UI** — mismas reglas de negocio (solo versión publicada, mismos roles, mismos códigos de error).  
2. **Polimórfico por `kind`** — un patrón común; el shape de I/O varía por app.  
3. **MVP = apuntar a proyecto publicado** — no enviar el esquema completo en cada request.  
4. **Sync para lotes chicos; async para lotes grandes**.  
5. **API es disparador**, junto a Upload, Watch, Scheduler y **Pipeline** — no sustituye FILE_OPS ni §2; puede ejecutar un job suelto **o** un pipeline compuesto.  
6. **Misma autorización que la UI** — la máquina no bypasea tenancy, versión publicada ni permisos sobre proyectos/pasos ([`FILE_PIPELINE.md`](FILE_PIPELINE.md) §6).  
7. **Auditable y operable** — cada request deja rastro (`trigger_source=api`); el cliente puede consultar, cancelar y descargar evidencia; el tablero UI **consume** esos runs.

---

## 2. Posicionamiento en la arquitectura

```text
Disparadores
├── UI (upload manual / ejecutar pipeline)
├── File Watch (llegada de archivo)     ← FILE_OPS
├── File Scheduler (cron / dependencia) ← FILE_OPS
└── PLATFORM API (HTTP)                 ← este documento
        ↓
   mode=job ──────────→ Job suelto (un kind)
   mode=pipeline ─────→ FILE PIPELINE orchestrator  ← [`FILE_PIPELINE.md`](FILE_PIPELINE.md)
        ↓
   Runner(s) de app(s): Gate · Pipe · Reverse · Match · Scout · Clean · Split/Merge
         (+ Repair · Profiler cuando existan)
```

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Verticales que la API **invoca** |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Ops + Job encadenable |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación multi-app; **la API puede ejecutar un pipeline completo** |
| [`APP_FACTORY.md`](APP_FACTORY.md) §2.3 | PLATFORM API entregada |

**No es** un vertical de archivos en el menú UF. **Sí es** capacidad de plataforma: consola de **clientes/keys** (US) + HTTP para cualquier `kind` ejecutable y `pipeline_id`.

---

## 3. Apps / kinds en alcance

La API debe estar **alineada y disponible** para toda app que el sistema pueda ejecutar como Job. Inventario actual y previsto:

| `kind` | App | ¿Ejecutable por API? | Salida principal |
|--------|-----|----------------------|------------------|
| `file_gate` | File Gate | **Sí** (cableado) | Estado + informe |
| `dms` | FilePipe | **Sí** (cableado) | Archivo transformado + informe |
| `reverse` | Reverse Studio | **Sí** (cableado) | Layout de envío + informe |
| `file_match` | File Match | **Sí** (cableado) | Informe conciliación (2 entradas) |
| `structure_scout` | Structure Scout | **Sí** (cableado) | Borrador estructura (JSON) |
| `workspace` | Worksheets | **Fuera de MVP API de archivos** | (otro dominio: records) |
| `file_clean` | File Clean | **Sí** (cableado) | Archivo limpio + log reglas |
| `file_split` / `file_merge` | Split/Merge | **Sí** (cableado) | Uno o N archivos |
| `file_repair` | File Repair | Catálogo; **no** en `POST /jobs/run` | Archivo reparado + auditoría |
| `data_profiler` | Data Profiler | Catálogo; **no** hasta runner | Informe estadístico |
| `file_pipeline` | File Pipeline | **Sí** (delega en orquestador) | Informe por paso + artifacts — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) |

> **`mode=pipeline`:** además del `kind` suelto, la API puede aceptar `pipeline_id` (definición publicada) y delegar en el orquestador FILE_PIPELINE. Ver [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §3 y EJ-06.

> **File Diff:** no hay `kind` `file_diff`. Comparación A vs B → `file_match`. Ver [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §3.

> Worksheets puede tener API de registros en otra fase; **este documento** se centra en el **Job de archivo** común a la suite de archivos.

---

## 4. Autenticación, tenancy y seguridad de proceso

La identidad humana (login, correo, 2FA) sigue en [`docs/security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md). Este apartado cubre **identidad de máquina** y reglas que la API no puede saltarse.

| Requisito | Notas |
|-----------|--------|
| Identidad de máquina | API key y/o OAuth2 client-credentials (decidir en implementación; ambos ligados a `Company`) |
| Tenant | Token ligado a **una** `Company`; sin lectura ni ejecución cruzada |
| Autorización | El principal debe poder **ejecutar** cada proyecto destino (equivalente GE o rol de servicio). En pipeline: **todos** los pasos o se deniega el run completo — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §6 |
| Definición operativa | Pipeline `inactive` / `in_progress` / sin versión publicada → 409 (mismo rechazo que UI / Watch / Scheduler) |
| Auditoría | Cada job: servicio, `correlation_id`, proyecto/pipeline, versión, hashes — detalle §10.2 |
| Secretos | Rotación y revocación; keys por entorno (sandbox ≠ prod); nunca loguear archivo ni celdas |

Sin auth de máquina + scope por compañía/proyecto, **no** debe ir a producción.

### 4.1 Scopes (propuesta)

Un token “dios de la compañía” no es aceptable. Mínimo:

| Scope | Permite |
|-------|---------|
| `jobs:run` | `POST /jobs/run` (kind suelto) |
| `pipeline:run` | Ejecutar definición publicada (`kind=file_pipeline` / `pipeline_id`) |
| `jobs:read` | `GET /jobs/{id}` y listado |
| `jobs:cancel` | Cancelar un job/run en curso |
| `artifacts:download` | GET informe / archivo de salida |

El scope de máquina **no** debe ser más permisivo que el rol UI equivalente (p. ej. CO: metadatos, sin bytes de artifact si la política de la app lo exige).

### 4.2 Integridad y amenazas de proceso

| Tema | Regla |
|------|--------|
| Solo publicado | Ejecución productiva = versión publicada del proyecto o del pipeline |
| Artifacts | URLs firmadas + TTL; no paths adivinables; mismo TTL que historial UI |
| PII | Logs de app/API: metadatos y hashes, no cuerpo ni celdas |
| Idempotencia | Mismo `Idempotency-Key` + mismo hash de entrada → mismo `job_id` (no reejecutar) |
| Cuotas | Rate limit y tamaño de archivo por compañía / API key; rechazo claro |
| Webhooks | Firma HMAC, URL en lista blanca (anti-SSRF), reintentos con backoff; secreto nunca en query |
| Replay / enumeración | IDs no secuenciales; GET de job ajeno o de otra compañía → 404/403 |
| Upload | Mismos límites de tipo/tamaño que intake UI |
| Dry-run | No efectos laterales de negocio; **no** entra en el pulso del dashboard (§10.3) |
| Scout / Repair | Misma política que UI (Scout no es prod; Repair exige contexto Gate) |

Cliente de máquina **no** es un UF con 2FA: es identidad de servicio. Sí exige compañía activa, paquete/feature flag y scopes. La API **no** inventa roles PA/ED/GE/CO; reutiliza el mapa de plataforma.

---

## 5. Contrato común (visión)

### 5.1 Entradas (request)

**Metadatos** (JSON o campos multipart):

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `kind` | Sí* | App a ejecutar (`file_gate`, `dms`, …) o `file_pipeline` |
| `project_slug` (o id) | Sí si job suelto | Proyecto de esa compañía |
| `pipeline_id` (o slug) | Sí si cadena | Definición de pipeline de la compañía — §5.4 |
| `version` | Sí** | `published` o número de versión publicada |
| `wait` | No | `sync` (default MVP) \| `async`. **No** confundir con job vs pipeline |
| `idempotency_key` | Recomendado | Evita duplicar el mismo lote (header `Idempotency-Key`) |
| `correlation_id` | Recomendado | Traza cliente ↔ API ↔ runner ↔ (pasos) |
| `dry_run` | No | Vista previa; no cuenta en dashboard; no efectos laterales |
| Opciones | Según kind | p. ej. slot A/B, flags de política |

\*Job suelto: `kind` de app. Cadena: `kind=file_pipeline` **o** el atajo [`FILE_PIPELINE.md`](FILE_PIPELINE.md) `mode=pipeline` + `pipeline_id` (equivalentes).  
\**En MVP solo versiones **publicadas** (igual que la UI de ejecución productiva).

Dos ejes que no se mezclan: **qué** ejecutar (`kind` / `pipeline_id`) y **cómo esperar HTTP** (`wait=sync|async`). Borradores antiguos usaban `mode` para ambos; en spec usar `wait` + `kind`/`pipeline_id`.

**Cuerpo:** archivo(s) en `multipart/form-data`.

| Kind | Archivos |
|------|----------|
| Gate, Pipe, Reverse, Scout, Clean… | 1 archivo (`file`) |
| Match | 2 archivos (`file_a`, `file_b`) |
| Merge | N archivos (`files[]`) |
| Pipeline | 1 o N según el primer paso (handoff: [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §8) |

### 5.2 Ejemplo de llamada (conceptual)

```http
POST /api/v1/jobs/run
Authorization: Bearer <token>
Idempotency-Key: erp-20260810-001
Content-Type: multipart/form-data

kind=file_gate
project_slug=nomina-mensual
version=published
file=<bytes>
```

### 5.3 Salidas (response) — forma común

```json
{
  "ok": true,
  "job_id": "a1b2c3…",
  "kind": "file_gate",
  "project_slug": "nomina-mensual",
  "version": "v3",
  "status": "accepted",
  "summary": { },
  "errors": [],
  "artifacts": {
    "report_url": "/api/v1/jobs/a1b2c3…/report",
    "output_url": null
  },
  "content_hash": "sha256:…",
  "links": {
    "self": "/api/v1/jobs/a1b2c3…"
  }
}
```

| Campo | Uso |
|-------|-----|
| `ok` | Atajo booleano de negocio (aceptado / útil según kind) |
| `status` | Estado de máquina del job/run (§5.5) |
| `errors[]` | Lista tipada (`row`, `field`, `code`, `message`) cuando aplique |
| `artifacts` | URLs firmadas o rutas API para informe / archivo(s) de salida |
| `job_id` | Correlación con historial UI, tablero y Archive. En pipeline: además `pipeline_run_id` |

### 5.4 `kind=file_pipeline` / `mode=pipeline`

La API **no** reimplementa la cadena: **delega** en el orquestador. Contrato de pasos, handoff, `on_error` y auditoría E2E: [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §3, §7, **§7.1** (no duplicar aquí).

```http
POST /api/v1/jobs/run
Authorization: Bearer <token>
Idempotency-Key: erp-20260812-001
Content-Type: multipart/form-data

kind=file_pipeline
pipeline_id=nomina-diaria
version=published
wait=async
file=<bytes>
```

Equivalente documentado en Pipeline EJ-06: `POST /api/v1/pipelines/{pipeline_id}/runs`.

Respuesta async típica (`202`): `pipeline_run_id`, `status: queued`, `links.self`. El `GET` posterior incluye `steps[]` (status, `app_job_id`, `error_code`, artifacts por paso) según el JSON de [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §7.

Rechazar si: definición no `active`, sin versión publicada, el cliente no puede ejecutar algún proyecto de los pasos, handoff inválido (ya validado al publicar).

Pipelines largos: **`wait=async` por defecto** (Fase B+).

### 5.5 Estados (job suelto vs pipeline)

| Superficie | Valores | Notas |
|------------|---------|--------|
| Job suelto (máquina) | `queued` · `running` · `completed` · `failed` · `cancelled` | Compartido con Watch/Scheduler |
| Gate (negocio) | `accepted` · `rejected` | Veredicto **dentro** de un job `completed`; HTTP 200 + `ok` true/false |
| Pipeline run | `queued` · `running` · `completed` · `failed` · `cancelled` | [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §4; paso: `pending` · `running` · `completed` · `failed` · `skipped` |

No usar `accepted` como estado de un pipeline run.

---

## 6. Sync vs async

| Modo | Cuándo | HTTP |
|------|--------|------|
| **Sync** (`wait=sync`) | Archivos chicos / dry-run / MVP | `200` con cuerpo completo al terminar |
| **Async** (`wait=async`) | Lotes grandes / pipelines | `202 Accepted` + `job_id` / `pipeline_run_id`; cliente consulta, cancela o recibe webhook |

```text
Async:
  POST /jobs/run → 202 { job_id, status: "queued" }
  GET  /jobs/{id} → status + artifacts cuando termine
  Webhook (opcional) → POST al callback del cliente
```

File Watch y Scheduler compartirán la misma máquina de estados de Job.

---

## 7. Ejemplo extremo a extremo — File Gate

### Escenario

El ERP envía cada mañana `nomina_20260810.txt`. Debe validarse contra el proyecto Gate `nomina-mensual` (versión publicada) antes de la carga.

### Entradas

| Pieza | Valor |
|-------|--------|
| Auth | Bearer token del servicio ERP |
| `kind` | `file_gate` |
| `project_slug` | `nomina-mensual` |
| `version` | `published` |
| Archivo | `nomina_20260810.txt` |
| Idempotency-Key | `erp-20260810-001` |

### Qué procesa el sistema

1. Autenticar compañía / servicio.  
2. Verificar permiso de ejecución en el proyecto.  
3. Resolver versión publicada del contrato.  
4. Intake del archivo + content hash.  
5. Parsear + validar (mismo motor que la UI).  
6. Persistir job + informe.  
7. Responder con estado y errores tipados.

### Salida — aceptado

```json
{
  "ok": true,
  "job_id": "a1b2c3…",
  "kind": "file_gate",
  "project_slug": "nomina-mensual",
  "version": "v3",
  "status": "accepted",
  "summary": {
    "rows_total": 1520,
    "rows_ok": 1520,
    "rows_error": 0
  },
  "content_hash": "sha256:…",
  "artifacts": {
    "report_url": "/api/v1/jobs/a1b2c3…/report",
    "output_url": null
  }
}
```

En Gate **no** hay archivo de negocio nuevo: la salida es **estado + informe**.

### Salida — rechazado

```json
{
  "ok": false,
  "job_id": "d4e5f6…",
  "status": "rejected",
  "summary": {
    "rows_total": 1520,
    "rows_ok": 1497,
    "rows_error": 23
  },
  "errors": [
    {
      "row": 143,
      "field": "fecha_pago",
      "code": "invalid_date",
      "message": "Formato esperado YYYY-MM-DD"
    }
  ],
  "artifacts": {
    "report_url": "/api/v1/jobs/d4e5f6…/report",
    "output_url": null
  }
}
```

### Mini historia

1. Analista publica contrato v3 en la UI.  
2. ERP a las 06:00 hace `POST` con el TXT.  
3. API valida con v3.  
4. Si `accepted` → ERP continúa; si `rejected` → alerta con filas malas.  
5. Queda `job_id` auditable (igual que un run manual).

---

## 8. Matriz de entradas / salidas por kind

| Kind | Entrada | Proceso | Salida principal |
|------|---------|---------|------------------|
| **File Gate** | 1 archivo | Validar vs contrato | Estado + informe errores |
| **FilePipe** | 1 archivo | Parse → map → rules → serialize | **Archivo transformado** + informe |
| **Reverse Studio** | 1 planilla | Entrada → layout publicado | **Archivo de envío** + informe |
| **File Match** | 2 archivos (A, B) | Cruce por clave / reglas | Informe conciliación |
| **Structure Scout** | 1 muestra | Detectar / proponer | JSON borrador estructura (no prod) |
| **File Clean** | 1 archivo | Reglas de limpieza | Archivo limpio + log |
| **File Split** | 1 archivo | Partición | N archivos |
| **File Merge** | N archivos | Consolidación | 1 archivo |
| **File Repair** | 1 archivo (+ contexto job Gate) | Correcciones auditadas | Archivo reparado + log |
| **Data Profiler** | 1 archivo | Perfil estadístico | Informe (puede no producir archivo de handoff) |
| **File Pipeline** | 1 o N (según paso 1) | Orquestar runners | Veredicto global + `steps[]` + artifacts |

> Comparar dos versiones / A vs B: usar **File Match**, no un kind Diff.

### Ejemplo mental FilePipe

| Entrada | Proceso | Salida |
|---------|---------|--------|
| `empleados.csv` + proyecto Pipe publicado | Mapeo + reglas + serializar | `empleados_erp.txt` + job OK/errores |

```json
{
  "ok": true,
  "kind": "dms",
  "status": "completed",
  "artifacts": {
    "output_url": "/api/v1/jobs/…/output",
    "report_url": "/api/v1/jobs/…/report"
  }
}
```

---

## 9. Modelo de errores

| Capa | Ejemplos | HTTP (orientativo) |
|------|----------|---------------------|
| Auth / tenant | Token inválido, compañía inactiva | 401 / 403 |
| Validación request | `kind` desconocido, falta archivo | 400 |
| Negocio proyecto / pipeline | Sin versión publicada, no `active`, sin permiso en un paso | 409 / 403 |
| Ejecución | Rechazo Gate, filas con error Pipe, paso de pipeline failed | 200 con `ok: false` **o** 422 (decidir en spec) |
| Infra | Timeout, storage | 503 / 500; preferir async |

Códigos de fila/campo deben **reutilizar** catálogos existentes (`ExecutionErrorCode`, mensajes UI) para no bifurcar semántica UI vs API.

---

## 10. Consulta, operación, webhooks, auditoría y dashboard

La API no sustituye diseñador, publicar, ayuda ni tablero. Superficie HTTP de **ejecutar + observar + cancelar + evidencia**.

### 10.1 Operación del cliente

| Mecanismo | Uso | Estado |
|-----------|-----|--------|
| `GET /api/v1/jobs/{id}` | Estado, auditoría de disparo, artifacts; si pipeline: `steps[]` | **Hecho** |
| `GET /api/v1/jobs` | Listado filtrable: kind, status, fechas, `api_client_id` | **Hecho** |
| `GET …/report` · `GET …/output` | Descarga (TTL, token, scope `artifacts:download`) | **Hecho** (output 404 si no hay un solo archivo) |
| `POST /api/v1/jobs/{id}/cancel` | Abortar async / pipeline en curso; Split/Merge/etc. terminal o no-cola → 409 | **Hecho** |
| `dry_run=true` en `POST …/run` | Misma validación; sin efectos laterales; excluido del pulso del tablero | **Hecho** (kinds que el runner lo admite) |
| Reintento | **Nuevo** run (nuevo `Idempotency-Key` o key distinta). Relacionar con `retry_of_job_id` / `retry_of_run_id` si el cliente lo envía | **Hecho** (campo en contrato) |
| Webhook `job.completed` / `job.failed` / `job.cancelled` | POST al callback del cliente (HMAC, allowlist, reintentos) | **Hecho** (M8) |

Payload de webhook mínimo: `job_id`, `kind` (o `pipeline_run_id`), `status`, `ok`, `correlation_id`, links a artifacts. Si pipeline: `failed_step_id` opcional. Firma HMAC (§4.2).

### 10.2 Auditoría del job API (hereda Pipeline §7.1)

**No duplicar** el modelo de definición + paso de [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §7.1. Aquí solo lo que es **HTTP / máquina**.

Todo job o pipeline run disparado por API debe persistir:

| Campo | Uso |
|-------|-----|
| `trigger_source` | Siempre `api` (el orquestador/UI usan `ui` \| `watch` \| `scheduler` \| `dependency`) |
| `triggered_by_api_client_id` | Identidad de la key/cliente OAuth |
| `idempotency_key` | Si vino en el request |
| `correlation_id` | Traza extremo a extremo |
| `job_id` y, si aplica, `pipeline_run_id` | El GET y la UI usan el mismo id |
| `app_job_id` por paso | Solo pipeline; el detalle fino sigue en el historial de cada app |
| `client_ip` / `user_agent` | Recomendable |
| Hashes de entrada / artifacts | Evidencia; no el contenido |
| Timing | `triggered_at` · `started_at` · `finished_at` · `duration_ms` |
| `dry_run` | Flag |

La API **no** audita el diseño de esquemas ni el editor de pipelines (CRUD fuera de MVP). Sí deja rastro de **cada ejecución**. El mismo registro debe verse en historial de la app o en detalle/auditoría del pipeline.

`GET /jobs/{id}` (scope `jobs:read`) expone estos metadatos al cliente que disparó (o a keys de la misma compañía con permiso de lectura). Eventos append-only; borrado = política PA / soft, igual que UI.

### 10.3 Relación con el dashboard

El tablero de Pipeline es **UI de compañía** ([`definition_app_FILE_PIPELINE/pipeline_dashboard.md`](definition_app_FILE_PIPELINE/pipeline_dashboard.md), ruta `/app/file-pipeline/tablero/`). Volumen, canales (`trigger_source`), fallos recientes; dry-run fuera del pulso; no mezcla compañías.

| Decisión | |
|----------|--|
| ¿La API sustituye el tablero? | **No** (MVP ni Fase C) |
| ¿Los runs `trigger_source=api` alimentan el tablero? | **Sí** — si no, ops no ve la carga del ERP |
| ¿Endpoint de métricas agregadas? | **No** en MVP. Fase posterior opcional: `GET /api/v1/ops/summary` con el **mismo** alcance de visibilidad que el tablero, nunca cross-tenant |

Jobs sueltos (Gate/Pipe sin pipeline) alimentan el **historial de esa app**, no el tablero de pipelines (salvo que el producto decida un tablero de plataforma unificado más adelante).

---

## 11. Límites e idempotencia

| Tema | Orientación |
|------|-------------|
| Tamaño de archivo | Alinear a límites de intake UI; rechazar con error claro |
| Timeout sync | Umbral bajo (p. ej. decenas de segundos); si se excede → forzar async |
| Idempotency-Key | Mismo key + mismo hash → devolver el mismo `job_id` sin reejecutar |
| Rate limit | Por compañía / API key |
| Retención artifacts | Misma política TTL que historial de la app |

---

## 12. Relación con FILE_OPS y otras piezas

| Pieza | Relación con PLATFORM_API |
|-------|---------------------------|
| **File Watch** | Disparador por llegada; internamente puede llamar al mismo runner que la API |
| **File Scheduler** | Disparador por tiempo; mismo runner |
| **File Archive** | Custodia E2E del `job_id` (entrada hash → salida hash) |
| **Schema Registry** | Fase posterior: `contract_id` además de `project_slug` |
| **File Clean / Repair / Profiler** | Clean + Split/Merge: `kind` en `/jobs/run`. Repair/Profiler: catálogo, no cableados |
| **File Pipeline** | `kind=file_pipeline`; mismo runner/orquestador que la UI; auditoría §7.1 del Pipeline |
| **Dashboard Pipeline** | UI; runs API con `trigger_source=api` entran al pulso (§10.3) |
| **Profile Seed** | Principalmente diseño/UI; ejecución API poco prioritaria |

```text
Watch ─┐
Sched ─┼→ runner de Job ←── PLATFORM API
UI    ─┘
```

---

## 13. Qué no es (MVP)

| Fuera de alcance MVP | Motivo |
|----------------------|--------|
| Enviar esquema/reglas completas en el body | Complejidad; usar proyecto publicado |
| CRUD de proyectos, miembros, billing, diseñador de pipeline | Otro superficie; la UI modela |
| API de métricas / tablero | El dashboard es pantalla; ver §10.3 |
| Sustituir ayuda / diseño visual | La UI sigue siendo el lugar de modelado |
| Worksheets records API completa | Dominio distinto; doc futuro si aplica |
| App “File Convert” vía API | Convert trivial = Pipe; no kind aparte |

---

## 14. Fases de entrega (roadmap vs código)

Las fases A/B/C eran el orden de diseño. **M1–M9 están en `apps.platform_api`.** Lo que sigue es backlog, no “aún no hay HTTP”.

### Fase A — MVP — **hecho**

- Auth de servicio + scopes (`jobs:run`, `jobs:read`, `jobs:cancel`, `pipeline:run`, `artifacts:download`) + aislamiento `Company`.  
- `POST /jobs/run` sync (y `wait=async` donde el runner lo admite).  
- Respuesta común + `errors[]` + `report_url` / `output_url` (token + TTL).  
- `GET /jobs/{id}` con actor API, hashes, timing (`trigger_source=api`).  
- Idempotency-Key.  
- Solo versión publicada.  
- PII: no loguear cuerpos.  
- Consola US: clientes, contrato, paths, integración, política, auditoría de cliente.

### Fase B — **hecho** (salvo kinds no cableados)

- Reverse Studio, File Match (2 archivos), Structure Scout.  
- `wait=async` + polling + `POST …/cancel`.  
- Listado `GET /jobs`.  
- `kind=file_pipeline` (delega; atajo `POST /pipelines/{pipeline_id}/runs`).  
- Dry-run en el contrato / runners que lo soportan.

### Fase C — **parcial**

| Pieza | Estado |
|-------|--------|
| Webhooks firmados (HMAC, allowlist, reintentos) | **Hecho** (M8) |
| File Clean + Split/Merge | **Hecho** |
| File Repair / Data Profiler | Catálogo; **no** ejecutables |
| Integración Archive + Schema Registry | **Pendiente** (FILE_OPS) |
| Índice OpenAPI en JSON (`GET /api/v1/openapi`) | **Hecho** (M9) |
| YAML OpenAPI 3 + SDKs | **Aplazado** |
| `GET /ops/summary` | **No** (tablero Pipeline cubre pulso) |

> El orden histórico (FILE_OPS primero, luego HTTP) ya se ejecutó: Clean/Split existen y la capa HTTP unificada está en producción de código. Repair/Profiler, Watch y Archive siguen fuera de esta app.

---

## 15. ¿Es algo funcional?

| Pregunta | Respuesta |
|----------|-----------|
| ¿Hace trabajo real? | **Sí** — valida/transforma/emite/concilia/parte con los motores actuales |
| ¿Reemplaza la UI? | **No** — la UI diseña; la API ejecuta |
| ¿Útil solo con Gate? | **Sí** — ya aporta valor de integración |
| ¿Depende de FILE_OPS para nacer? | **No**; Watch/Archive lo potencian después |
| ¿Alineado a todas las apps? | **Sí**, por `kind`; Repair/Profiler aún no |
| ¿Consume Pipeline? | **Sí** — delega; no reimplementa |

---

## 16. Criterio de aceptación

Cubierto en código (M1–M9) y recorrido en el manual de jobs sueltos (curl 1–10). Pendiente de producto: circuito HTTP de **pipelines** (manual placeholder), YAML OpenAPI, kinds Repair/Profiler.

1. Un solo runner de Job reutilizado por UI / API / (futuro) Watch.  
2. Contrato común + matriz por `kind` + `kind=file_pipeline` (delega).  
3. Auth de máquina + scopes + aislamiento por `Company`; pipeline: permiso en cada paso.  
4. Solo versión publicada; pipeline no `active` rechazado.  
5. Códigos de error alineados al catálogo UI.  
6. Gate + Pipe (y el resto cableado) antes de exigir YAML.  
7. Límites de tamaño/TTL, tokens de artifact, PII en logs.  
8. Auditoría §10.2: `trigger_source=api`, cliente, idempotency, correlation, hashes; pipeline hereda [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §7.1.  
9. El mismo job/run visible en historial UI / detalle pipeline.  
10. Cancel: 200 solo si el runner/cola lo permite; 409 en Split completed (circuito de prueba).

---

## 17. Próximos pasos

1. Mantener este archivo como **paraguas** (estado = código, no “diseño vacío”).  
2. Specs: [`definition_app_PLATFORM_API/`](definition_app_PLATFORM_API/). Manual pipelines: [`MANUAL_USUARIO_API_PIPELINE.md`](definition_app_PLATFORM_API/MANUAL_USUARIO_API_PIPELINE.md).  
3. YAML OpenAPI 3 / SDKs si producto lo pide.  
4. Cablear `file_repair` / `data_profiler` cuando existan runners.  
5. No duplicar orquestación: puntero a [`FILE_PIPELINE.md`](FILE_PIPELINE.md).

---

## 18. Glosario

| Término | Definición |
|---------|------------|
| **PLATFORM_API** | Capa HTTP de ejecución remota de jobs |
| **Job** | Unidad auditable: entrada(s) + versión + resultado + artifacts |
| **kind** | Discriminador de app (`file_gate`, `dms`, `reverse`, `file_pipeline`, …) |
| **wait** | `sync` \| `async` — cómo espera el HTTP; distinto de job vs pipeline |
| **Runner** | Servicio interno que ejecuta el job (compartido UI/API/Watch) |
| **Artifact** | Informe o archivo de salida descargable (URL firmada + TTL) |
| **Idempotency-Key** | Clave de cliente para no duplicar ejecuciones |
| **correlation_id** | Traza entre cliente, API, orquestador y jobs de app |
| **trigger_source** | Canal; en esta API siempre `api` |
| **Scope** | Permiso de la credencial de máquina (`jobs:run`, `pipeline:run`, …) |
| **Versión publicada** | Única definición ejecutable en productivo (UI y API) |

---

## 19. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY.md`](APP_FACTORY.md) | Índice; PLATFORM API en §2.3 |
| [`definition_app_PLATFORM_API/`](definition_app_PLATFORM_API/) | Specs M1–M9 **implementados**; manuals de uso |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Ops; Job encadenable; Watch/Scheduler como hermanos disparadores |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación; API `kind=file_pipeline`; **auditoría E2E §7.1** (heredar); seguridad §6 |
| [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) | Disparo por tiempo; `trigger_source=scheduler`; auditoría/errores propios en FILE_SCHEDULER §7–§8 |
| [`definition_app_FILE_PIPELINE/pipeline_dashboard.md`](definition_app_FILE_PIPELINE/pipeline_dashboard.md) | Tablero UI; runs API alimentan el pulso (§10.3) |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Verticales §2 que la API invoca |
| [`FILE_GATE.md`](FILE_GATE.md) | Primer kind MVP de validación |
| [`DataMappingStudio.md`](DataMappingStudio.md) | FilePipe / motor ETL |
| [`REVERSE_STUDIO.md`](REVERSE_STUDIO.md) | Emisión |
| [`FILE_MATCH.md`](FILE_MATCH.md) | Conciliación A/B |
| [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) | Exploración de muestra |
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Producto; API REST Fase 3 |
| [`docs/security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md) | Base de auth (extender a máquina) |
| [`docs/definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | Alinear `error_code` / mensajes |

---

*Documento vivo. Actualizar §3 y §14 cuando un kind nuevo sea ejecutable. Código: `apps.platform_api`.*
