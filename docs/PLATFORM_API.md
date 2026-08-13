# PLATFORM API — Ejecución remota de jobs

> **Nombre mnemotécnico:** `PLATFORM_API`  
> Alias: *API de jobs* · *API de integración* · *Ejecución remota*  
> Archivo: [`docs/PLATFORM_API.md`](PLATFORM_API.md)  
> Estado: **propuesta de producto / diseño** (sin implementación)  
> **Cuándo implementar:** **después** de finalizar el desarrollo de las apps FILE_OPS (Clean, Split/Merge, Profiler, …). Las apps nacen API-ready; la capa HTTP se unifica al cierre.  
> Padres: [`APP_FACTORY.md`](APP_FACTORY.md) §4 · [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) (disparadores)  
> Alcance: **todas las apps ejecutables** que el sistema pueda manejar vía Job (Gate, Pipe, Reverse, Match, Scout, y FILE_OPS)  
> Primer kind FILE_OPS en diseño: [`FILE_CLEAN.md`](FILE_CLEAN.md) (`kind=file_clean`)

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
| **Preparar implementación** | Fases MVP, auth, sync/async, webhooks, límites |

### Alcance (sí / no)

| Sí | No |
|----|-----|
| Ejecutar **versión publicada** de un proyecto existente | Sustituir la UI de diseño de esquemas/mapeos |
| Cubrir **todos los kinds ejecutables** con el mismo patrón | Un endpoint distinto “de producto” por app sin contrato común |
| Auth de máquina, idempotencia, informe, descarga | CRUD completo de proyectos/miembros vía API en MVP |
| Relación con Watch / Scheduler / Archive | Spec OpenAPI final ni código Django |

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
| [`APP_FACTORY.md`](APP_FACTORY.md) §4 | “API / Webhooks” de plataforma |

**No es** una app del sidebar. **Sí es** capacidad de plataforma disponible para **cualquier** `project_kind` ejecutable y, previsto, para **`pipeline_id`**.

---

## 3. Apps / kinds en alcance

La API debe estar **alineada y disponible** para toda app que el sistema pueda ejecutar como Job. Inventario actual y previsto:

| `kind` | App | ¿Ejecutable por API? | Salida principal |
|--------|-----|----------------------|------------------|
| `file_gate` | File Gate | Sí (prioridad MVP) | Estado + informe |
| `dms` | FilePipe | Sí (prioridad MVP) | Archivo transformado + informe |
| `reverse` | Reverse Studio | Sí | Layout de envío + informe |
| `file_match` | File Match | Sí | Informe conciliación (2 entradas) |
| `structure_scout` | Structure Scout | Sí (explorar muestra) | Borrador estructura (JSON) |
| `workspace` | Worksheets | **Fuera de MVP API de archivos** | (otro dominio: records) |
| `file_clean` | File Clean | Sí | Archivo limpio + log reglas |
| `file_split` / `file_merge` | Split/Merge | Sí | Uno o N archivos |
| `file_repair` | File Repair | Sí | Archivo reparado + auditoría |
| `file_pipeline` | File Pipeline | Sí (orquestación) | Informe por paso + artifacts finales — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) |

> **`mode=pipeline`:** además del `kind` suelto, la API puede aceptar `pipeline_id` (definición publicada) y delegar en el orquestador FILE_PIPELINE. Ver [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §3 y EJ-06.

> **File Diff:** no hay `kind` `file_diff`. Comparación A vs B → `file_match`. Ver [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §8.

> Worksheets puede tener API de registros en otra fase; **este documento** se centra en el **Job de archivo** común a la suite de archivos.

---

## 4. Autenticación y tenancy

| Requisito | Notas |
|-----------|--------|
| Identidad de máquina | API key / token OAuth2 client-credentials (decidir en implementación) |
| Tenant | Token ligado a `Company`; sin lectura cruzada |
| Autorización | El principal debe poder **ejecutar** (equivalente GE o rol de servicio) en el proyecto |
| Auditoría | Cada job registra *quién* (servicio), *cuándo*, *proyecto*, *versión*, *hash* |
| Secretos | Rotación de keys; nunca loguear el archivo completo en claro en logs de app |

Sin auth de máquina + scope por compañía/proyecto, **no** debe ir a producción.

---

## 5. Contrato común (visión)

### 5.1 Entradas (request)

**Metadatos** (JSON o campos multipart):

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `kind` | Sí | App a ejecutar (`file_gate`, `dms`, `reverse`, `file_match`, …) |
| `project_slug` (o id) | Sí | Proyecto de esa compañía |
| `version` | Sí* | `published` o número de versión publicada |
| `mode` | No | `sync` (default MVP) \| `async` |
| `idempotency_key` | Recomendado | Evita duplicar el mismo lote |
| Opciones | Según kind | p. ej. `dry_run`, slot A/B, flags de política |

\*En MVP solo se aceptan versiones **publicadas** (igual que la UI de ejecución productiva).

**Cuerpo:** archivo(s) en `multipart/form-data`.

| Kind | Archivos |
|------|----------|
| Gate, Pipe, Reverse, Scout, Clean… | 1 archivo (`file`) |
| Match | 2 archivos (`file_a`, `file_b`) |
| Merge | N archivos (`files[]`) |

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
| `status` | Máquina de estados del job (`accepted`, `rejected`, `completed`, `failed`, `queued`…) |
| `errors[]` | Lista tipada (`row`, `field`, `code`, `message`) cuando aplique |
| `artifacts` | URLs firmadas o rutas API para informe / archivo(s) de salida |
| `job_id` | Correlación con historial UI y Archive futuro |

---

## 6. Sync vs async

| Modo | Cuándo | HTTP |
|------|--------|------|
| **Sync** | Archivos chicos / dry-run / MVP | `200` con cuerpo completo al terminar |
| **Async** | Lotes grandes / pipelines largos | `202 Accepted` + `job_id`; cliente consulta o recibe webhook |

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
| Negocio proyecto | Sin versión publicada, sin membresía | 409 / 403 |
| Ejecución | Rechazo Gate, filas con error Pipe | 200 con `ok: false` **o** 422 (decidir en spec) |
| Infra | Timeout, storage | 503 / 500; preferir async |

Códigos de fila/campo deben **reutilizar** catálogos existentes (`ExecutionErrorCode`, mensajes UI) para no bifurcar semántica UI vs API.

---

## 10. Webhooks y consulta

| Mecanismo | Uso |
|-----------|-----|
| `GET /api/v1/jobs/{id}` | Polling de estado y artifacts |
| `GET …/report` · `GET …/output` | Descarga informe / archivo (TTL alineado a historial UI) |
| Webhook `job.completed` / `job.failed` | Notificar URL del cliente (Fase 2) |

Payload de webhook mínimo: `job_id`, `kind`, `status`, `ok`, links a artifacts.

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
| **File Clean / Repair** | Nuevos `kind` en el mismo endpoint `/jobs/run` |
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
| CRUD de proyectos, miembros, billing | Otro superficie API |
| Sustituir ayuda / diseño visual | La UI sigue siendo el lugar de modelado |
| Worksheets records API completa | Dominio distinto; doc futuro si aplica |
| App “File Convert” vía API | Convert trivial = Pipe; no kind aparte |

---

## 14. Fases de entrega (roadmap)

### Fase A — MVP (funcional de verdad)

- Auth de servicio + scope compañía.  
- `POST /jobs/run` sync para **File Gate** y **FilePipe**.  
- Respuesta común + `errors[]` + `report_url` / `output_url`.  
- `GET /jobs/{id}` básico.  
- Idempotency-Key.  
- Misma validación “solo versión publicada”.

### Fase B

- **Reverse Studio** + **File Match** (2 archivos).  
- Modo **async** + polling.  
- Structure Scout (salida JSON borrador).

### Fase C

- Webhooks.  
- Kinds FILE_OPS (**File Clean** y siguientes) — las apps ya deben exponer runner + artifacts.  
- Integración Archive + opcional Schema Registry.  
- OpenAPI publicada / SDKs opcionales.

> **Orden de programa:** completar verticales FILE_OPS (empezando por Clean) **antes** de abrir implementación de esta API. Hasta entonces, solo diseño y requisitos API-ready en cada app.

---

## 15. ¿Es algo funcional?

| Pregunta | Respuesta |
|----------|-----------|
| ¿Hace trabajo real? | **Sí** — valida/transforma/emite/concilia con los motores actuales |
| ¿Reemplaza la UI? | **No** — la UI diseña; la API ejecuta |
| ¿Útil solo con Gate? | **Sí** — ya aporta valor de integración |
| ¿Depende de FILE_OPS para nacer? | **No**; FILE_OPS (Watch/Archive) lo potencia después |
| ¿Alineado a todas las apps? | **Sí**, por diseño: mismo runner, `kind` discriminador |

---

## 16. Criterio de aceptación (antes de implementar)

1. ¿Un solo runner de Job reutilizado por UI / API / (futuro) Watch?  
2. ¿Contrato común + matriz por `kind` documentada?  
3. ¿Auth de máquina + aislamiento por `Company`?  
4. ¿Solo versión publicada en ejecución productiva?  
5. ¿Códigos de error alineados al catálogo UI?  
6. ¿MVP acotado (Gate + Pipe sync) antes de webhooks?  
7. ¿Límites de tamaño/TTL definidos?

---

## 17. Próximos pasos de diseño

1. Mantener este archivo como **paraguas PLATFORM_API**.  
2. Al priorizar implementación: OpenAPI borrador + `definition_app` o carpeta `docs/definition_app_PLATFORM_API/` si hace falta.  
3. Spike: extraer “run published project” compartido desde vistas actuales de Gate/Pipe.  
4. Actualizar [`APP_FACTORY.md`](APP_FACTORY.md) §8 cuando pase a definición / en curso / hecho.  
5. No duplicar el contrato completo dentro de cada `FILE_*.md` — solo puntero aquí.

---

## 18. Glosario

| Término | Definición |
|---------|------------|
| **PLATFORM_API** | Capa HTTP de ejecución remota de jobs |
| **Job** | Unidad auditable: entrada(s) + versión + resultado + artifacts |
| **kind** | Discriminador de app (`file_gate`, `dms`, `reverse`, …) |
| **Runner** | Servicio interno que ejecuta el job (compartido UI/API/Watch) |
| **Artifact** | Informe o archivo de salida descargable |
| **Idempotency-Key** | Clave de cliente para no duplicar ejecuciones |
| **Versión publicada** | Única definición ejecutable en productivo (UI y API) |

---

## 19. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY.md`](APP_FACTORY.md) | Visión; §4 API/Webhooks; prioridad plataforma |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Ops; Job encadenable; Watch/Scheduler como hermanos disparadores |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación multi-app; API `mode=pipeline` / `kind=file_pipeline` |
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

*Documento vivo. Actualizar §3, §14 y §19 cuando un kind nuevo sea ejecutable o la API pase a implementación.*
