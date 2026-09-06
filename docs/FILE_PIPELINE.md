# FILE PIPELINE — Orquestación de flujos multi-app

> **Nombre mnemotécnico:** `FILE_PIPELINE`  
> Alias: *Pipeline* · *Orquestador de archivos* · *Flujo encadenado* · *Job compuesto*  
> Archivo: [`docs/FILE_PIPELINE.md`](FILE_PIPELINE.md)  
> Estado: **MVP hecho** (M1–M5 + tablero) · `apps.file_pipeline` · `main`  
> Disparadores: UI, Watch, Scheduler, PLATFORM API (`kind=file_pipeline`)  
> Padres: [`APP_FACTORY.md`](APP_FACTORY.md) · [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §15 (Job encadenable)  
> Hermano disparador/consumidor: [`PLATFORM_API.md`](PLATFORM_API.md) — **la API puede ejecutar un Pipeline completo**, no solo un `kind` suelto  
> Alcance: **desarrollo global** que consume apps §2 + FILE_OPS + capas de plataforma (Watch, Scheduler, Archive, Registry)  
> Specs por módulo: [`definition_app_FILE_PIPELINE/`](definition_app_FILE_PIPELINE/)

### Rama de desarrollo

| Ítem | Valor |
|------|--------|
| **Rama Git** | `main` (MVP mergeado; origen histórico `Mejoras_FILE_PIPELINE` / `_v2`) |
| **Base** | `main` |
| **Despliegues Railway** | Desde **`main`** |

---

## Mapa de specs

| Módulo | Spec | Prototipo |
|--------|------|-----------|
| 1 Ciclo de pipeline | [`definition_app_FILE_PIPELINE/project_lifecycle.md`](definition_app_FILE_PIPELINE/project_lifecycle.md) | listado / alta / hub |
| 2 Diseñador | [`definition_app_FILE_PIPELINE/pipeline_designer.md`](definition_app_FILE_PIPELINE/pipeline_designer.md) | `pipeline_designer.html` |
| 2b Step Catalog | [`definition_app_FILE_PIPELINE/pipeline_catalog.md`](definition_app_FILE_PIPELINE/pipeline_catalog.md) | `pipeline_catalog*.html` |
| 3 Publicar | [`definition_app_FILE_PIPELINE/pipeline_publish.md`](definition_app_FILE_PIPELINE/pipeline_publish.md) | `pipeline_publish.html` |
| 4 Ejecutar | [`definition_app_FILE_PIPELINE/pipeline_run.md`](definition_app_FILE_PIPELINE/pipeline_run.md) | run / result |
| 5 Historial | [`definition_app_FILE_PIPELINE/pipeline_history.md`](definition_app_FILE_PIPELINE/pipeline_history.md) | history / detail |
| D Dashboard | [`definition_app_FILE_PIPELINE/pipeline_dashboard.md`](definition_app_FILE_PIPELINE/pipeline_dashboard.md) | `pipeline_dashboard.html` |
| Transversal | [`definition_app_FILE_PIPELINE/fp_integration.md`](definition_app_FILE_PIPELINE/fp_integration.md) | — |

Índice: [`definition_app_FILE_PIPELINE/README.md`](definition_app_FILE_PIPELINE/README.md).

---

## 0. Para qué sirve este documento

### Qué es

Documento de **plataforma** (no un vertical de menú aislado) que define cómo el usuario (o un sistema externo) **compone un flujo** de pasos — cada paso = ejecución de una app con su versión publicada — de modo que **un archivo pase por varios tratamientos** y el sistema reporte **OK / Error por etapa** y un veredicto global.

Ejemplo mental:

```text
FILE_CLEAN → FILE_MERGE → FILE_GATE → (opcional) FILEPIPE / MATCH
```

### Qué función cumple

| Función | Descripción |
|---------|-------------|
| **Congelar la visión** | Habrá un orquestador de pipelines, no solo jobs sueltos por app |
| **Delimitar** | Pipeline ≠ app de Clean/Gate; Pipeline **invoca** runners existentes |
| **Unificar contrato** | Definición de flujo + run + pasos + artifacts + errores tipados |
| **Preparar implementación** | Fases MVP, UI diseñador, disparadores, relación con API |
| **No perder el análisis** | Base para un desarrollo que consume **toda** la suite |

### Alcance (sí / no)

| Sí | No |
|----|-----|
| Diseñar / versionar / publicar un **pipeline** (lista ordenada de pasos) | Reescribir parsers o reglas de cada app |
| Ejecutar el pipeline (UI, Watch, Scheduler, **PLATFORM_API**) | Sustituir el historial local de cada app (Archive lo unifica después) |
| Pasar artifacts entre pasos (referencia / storage, sin re-upload manual) | Editor de mapeo ETL dentro del pipeline (eso sigue en Pipe/Reverse) |
| Política por paso: stop on error, continue, branch futuro | Spec OpenAPI final ni código Django en este doc |
| Relación explícita con PLATFORM_API, Watch, Scheduler, Archive | Obligatoriedad de Schema Registry en MVP |

### En una frase

**Las apps diseñan y publican su definición; el Pipeline decide el orden, ejecuta la cadena y reporta OK/Error por paso.**

---

## 1. Resumen ejecutivo

### Problema

Hoy el encadenamiento es **manual**:

```text
Clean (descarga) → usuario sube a Merge → descarga → usuario sube a Gate → …
```

Eso no escala: no hay veredicto E2E, no hay corte automático si un paso falla, y Watch/API solo podrían disparar **un** job suelto.

### Solución

Capa de **orquestación**:

```text
Definir Pipeline (pasos + proyectos/versiones + políticas)
        →
Publicar definición de pipeline (inmutable en run)
        →
Disparar (UI · Watch · Scheduler · PLATFORM_API)
        →
Ejecutar paso 1 → artifact → paso 2 → … 
        →
Informe: por paso OK|ERROR + estado global + artifacts finales
```

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Beneficio** | Un archivo recibe varios tratamientos sin operador entre apps; auditoría E2E |
| **Audiencia** | Ops, integración, calidad, IT, partners (vía API) |
| **Diferenciador** | Orquesta **toda la suite** con el mismo Job/runner por app |
| **Reuso** | 100 % de runners existentes (`run_*_job`); Pipeline no reimplementa motores |

### Principios de diseño

1. **Misma seguridad que la plataforma** — Company + roles PA/ED/GE/CO + scopes API; solo autorizados actúan (§6 seguridad).  
2. **Pipeline invoca; no duplica** — cada paso llama al runner de la app (`kind` + proyecto + versión publicada).  
2. **Misma semántica que la UI de cada app** — solo versión publicada; mismos `error_code` / mensajes.  
3. **Artifacts por referencia** — salida del paso N = entrada del N+1 (storage), no Excel de ida y vuelta.  
4. **Informe por paso + global** — el usuario ve dónde falló la cadena.  
5. **Disparadores múltiples** — UI, Watch, Scheduler y **PLATFORM_API pueden consumir el Pipeline**.  
6. **MVP acotado** — cadena lineal + stop-on-error; ramas/condiciones = fase 2.

---

## 2. Posicionamiento en la arquitectura

```text
Disparadores
├── UI (diseñar + ejecutar pipeline)
├── File Watch (llegada → pipeline_id)
├── File Scheduler (cron / “tras A” → pipeline_id)
└── PLATFORM API (HTTP → pipeline_id o kind suelto)
        ↓
   FILE PIPELINE  (orquestador)          ← este documento
        ↓
   Paso 1 → Paso 2 → … → Paso N
        ↓         ↓
   Runner app   Runner app   (Gate, Clean, Split/Merge, Pipe, …)
        ↓
   (opcional) File Archive  ← expediente E2E
   (opcional) Notify
```

| Capacidad | Rol respecto al Pipeline |
|-----------|--------------------------|
| Apps §2 + FILE_OPS | **Pasos** ejecutables (`kind`) |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Dispara un **pipeline completo** o un job suelto; idealmente reutiliza el mismo orquestador |
| [`FILE_WATCH.md`](FILE_WATCH.md) | Origen → `pipeline_id` publicado |
| [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) | Cron / dependencia → `pipeline_id`; auditoría CRUD+tick y `schedule_*` (no duplicar §7.1) |
| [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md) | Custodia del run E2E (hashes por paso) |
| [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) | Resolver contratos compartidos en pasos (fase posterior) |

**No es** (solo) un `project_kind` más de archivo. **Sí es** capacidad de plataforma que **compone** proyectos existentes.

---

## 3. Relación con PLATFORM_API

```text
Cliente externo
      ↓
PLATFORM API
      ├── mode=job      → un kind (Gate, Clean, …)     [ya propuesto en PLATFORM_API]
      └── mode=pipeline → pipeline_id + archivo(s)     [este documento]
                ↓
         FILE PIPELINE orchestrator
                ↓
         runners por paso
```

| Decisión | Contrato |
|----------|----------|
| API **puede consumir** Pipeline | Sí — endpoint (o `kind=file_pipeline`) que ejecuta la definición publicada |
| Pipeline **no depende** de la API para nacer | Sí — UI primero; API después o en paralelo |
| Un solo motor | PLATFORM_API no reimplementa la cadena: **delega** al orquestador Pipeline |
| Job suelto vs cadena | API sigue pudiendo llamar un solo `kind` (sin pipeline) para casos simples |

Detalle de auth, sync/async, webhooks: heredar de [`PLATFORM_API.md`](PLATFORM_API.md); aquí solo el shape de **pipeline run**.

---

## 4. Conceptos

| Concepto | Definición |
|----------|------------|
| **Pipeline definition** | Plantilla versionable: nombre, **estado operativo**, pasos ordenados, políticas, disparadores permitidos |
| **Pipeline version** | Snapshot publicado (inmutable) usado en un run |
| **Step** | Un eslabón: `kind` + `project_slug` (o id) + versión publicada (o “activa”) + opciones |
| **Pipeline run** | Ejecución concreta de una versión + entrada(s) + estado global |
| **Step run** | Resultado de un paso: status, job_id de la app, metrics, errors, artifact refs |
| **Artifact** | Archivo(s) / informe producidos por un paso; entrada tipada del siguiente |
| **Handoff** | Regla de paso de salida → entrada (1 archivo, N partes Split, 2 entradas Match, …) |

### Modelo mental de estados

Hay **tres niveles** que no se mezclan en UI ni en persistencia:

| Nivel | Campo | Valores (MVP) | Qué describe |
|-------|--------|----------------|--------------|
| **Definición** | `PipelineDefinition.status` | `active` · `in_progress` · `inactive` | Ciclo de vida del pipeline como objeto de trabajo |
| Step (run) | `status` | `pending` · `running` · `completed` · `failed` · `skipped` | Un eslabón de una corrida |
| Pipeline run | `status` | `queued` · `running` · `completed` · `failed` · `cancelled` | Una corrida concreta |

**Regla MVP (run):** si un paso `failed` y política = `stop` → run `failed`; pasos siguientes `skipped`.

#### Estado de la definición (`status`)

Campo **obligatorio** en cada pipeline. Independiente de si hay versión publicada y del resultado del último run.

| Valor | UI | Significado |
|-------|-----|-------------|
| `active` | Activo | En operación. Puede dispararse (UI / Watch / Scheduler / API) si además hay **versión publicada activa**. |
| `in_progress` | En proceso | Aún se diseña o no está listo para operación (borrador, sin publicar, o publicado pero no puesto en marcha). No acepta disparos automáticos. |
| `inactive` | Inactivo | Pausado a propósito. No se dispara por ningún canal hasta reactivar. La definición y el historial se conservan. |

Transiciones (PA del pipeline):

```text
Alta → in_progress
in_progress → active     (requiere versión publicada; si no, se rechaza)
active → inactive        (pausa)
inactive → active        (reactivar; misma regla de versión publicada)
inactive → in_progress   (vuelve a diseño)
active → in_progress     (sacar de operación para redefinir; runs en curso no se cancelan solos)
```

El listado filtra por este campo (**Todos / Activo / En proceso / Inactivo**). La versión publicada se muestra en la tabla y se gestiona en el hub; no es filtro del listado.

---

## 5. Anatomía de un paso

```json
{
  "step_id": "s2",
  "order": 20,
  "label": "Validar nómina",
  "kind": "file_gate",
  "project_ref": { "slug": "gate-nomina-banco" },
  "version": "published",
  "on_error": "stop",
  "input_from": "previous",
  "options": {}
}
```

| Campo | Notas |
|-------|--------|
| `kind` | Discriminador de app (misma matriz que PLATFORM_API) |
| `project_ref` | Proyecto existente de la compañía con ese `project_kind` |
| `version` | MVP: siempre versión **publicada activa** del proyecto |
| `on_error` | `stop` (MVP) · `continue` (fase 2) · `goto:step_id` (fase 2) |
| `input_from` | `pipeline_input` · `previous` · `step:<id>` · `static` (raro) |
| `options` | Overrides mínimos por kind (p. ej. Match: cuál artifact es A/B) |

### Matriz de kinds (pasos)

| `kind` | App | Entrada típica al paso | Salida típica |
|--------|-----|------------------------|---------------|
| `file_clean` | File Clean | 1 archivo | 1 limpio + log |
| `file_split` | Split/Merge (split) | 1 archivo | N partes + ZIP/manifiesto |
| `file_merge` | Split/Merge (merge) | ≥2 archivos | 1 consolidado |
| `file_gate` | File Gate | 1 archivo | veredicto + informe |
| `dms` | FilePipe | 1 archivo | transformado + informe |
| `reverse` | Reverse Studio | 1 archivo | layout emisión + informe |
| `file_match` | File Match | 2 archivos (A/B) | informe conciliación |
| `structure_scout` | Structure Scout | 1 muestra | JSON estructura (uso limitado en cadena) |
| `file_repair` | File Repair (si existe) | 1 + contexto Gate | repaired + auditoría |
| `data_profiler` | Data Profiler (si existe) | 1 archivo | informe estadístico (puede no alterar archivo) |

> Esta tabla es el **inventario de producto**. En runtime el diseñador **no** lista “todas las apps del menú”: solo las inscritas en el **catálogo de pasos** (§5.1).  
> Split en medio de una cadena exige regla de handoff: ¿el siguiente paso procesa **cada parte** (fan-out) o solo el ZIP? Ver §8.

### 5.1 Catálogo de apps disponibles para el Pipeline (mantenimiento)

#### Cómo sabe el Pipeline qué apps ofrecer

El diseñador de pipelines obtiene los pasos posibles de un **registro de plataforma** (“Pipeline Step Catalog” / `pipeline_step_kinds`), no de un `INSTALLED_APPS` a ciegas.

```text
App existe en el producto (menú / project_kind)
        ↓
¿Está inscrita como pipeline-capable?  ──No──→ No aparece en el diseñador
        │ Sí
        ↓
¿La compañía tiene el paquete / feature flag?  ──No──→ No aparece (o deshabilitada)
        │ Sí
        ↓
¿Hay runner + contrato de handoff (entrada/salida)?  ──No──→ No aparece / error de config
        │ Sí
        ↓
Visible en el picker de pasos → luego se eligen proyectos de ese kind
```

En UI:

1. Usuario elige **tipo de paso** (`kind` del catálogo).  
2. El sistema lista **solo proyectos** de esa compañía con ese `project_kind`, publicados y que el usuario pueda ejecutar.  
3. Validación al guardar/publicar: `kind` ∈ catálogo habilitado + proyecto coherente.

#### Qué contiene cada entrada del catálogo (mantenimiento)

| Campo | Uso |
|-------|-----|
| `kind` | Código estable (`file_gate`, `file_clean`, …) |
| `label` / descripción | Texto en el diseñador |
| `project_kind` | Debe coincidir con `Project.project_kind` |
| `runner` | Referencia al servicio `run_*_job` |
| `input_arity` | `1` · `2` · `N` (Merge) · `foreach` (fase 2) |
| `output_arity` | `1` · `N` (Split) · `none` (solo informe) |
| `produces_file` | Si alimenta el handoff de datos al siguiente paso |
| `pipeline_enabled` | **Opt-in**: `true` = disponible en Pipeline |
| `mvp_phase` | `A` / `B` / `C` (rollout) |
| `status` | `active` · `deprecated` · `disabled` |

Fuente de verdad de diseño: esta matriz + [`PLATFORM_API.md`](PLATFORM_API.md) kinds. Fuente de verdad de runtime: registro en código/config (p. ej. dict/settings o tabla de plataforma) leído por el diseñador y por el orquestador.

#### ¿Crear una app nueva la incorpora sola?

**No.** Regla de producto:

| Situación | ¿Aparece en Pipeline? |
|-----------|------------------------|
| Nueva app en menú, sin registrar en catálogo | **No** |
| App registrada con `pipeline_enabled=false` | **No** (existe, pero excluida a propósito) |
| App registrada, sin runner/handoff listo | **No** (o bloqueada hasta checklist) |
| App registrada + runner + handoff + flag compañía | **Sí** |

Así se puede lanzar un vertical (p. ej. Profiler, Repair, Formularios) **sin** comprometer el orquestador hasta que el paso esté maduro.

#### Cómo se incorpora una app nueva (checklist)

Al cerrar un vertical que deba ser paso de Pipeline:

1. Definir `kind` (alineado a PLATFORM_API).  
2. Exponer **runner** sin acoplar solo a vistas HTML.  
3. Documentar **handoff** (qué artifact es `output` / `report`).  
4. Añadir fila a la matriz de este doc y a PLATFORM_API.  
5. Registrar en el **Pipeline Step Catalog** con `pipeline_enabled=true` (o `false` hasta OK de producto).  
6. Habilitar por **paquete / feature flag** de compañía si aplica.  
7. Prueba: diseñador muestra el kind → proyecto → run de un pipeline de 1–2 pasos.  
8. Actualizar [`APP_FACTORY.md`](APP_FACTORY.md) / FILE_OPS estado.

#### Cómo se retira o limita

| Acción | Efecto |
|--------|--------|
| `pipeline_enabled=false` o `status=disabled` | No se ofrecen en **nuevos** diseños |
| `status=deprecated` | Pipelines ya publicados siguen; aviso al editar; no recomendar en picker |
| Quitar paquete a la compañía | Proyectos/pasos de ese kind dejan de ser seleccionables para esa compañía |
| App borrada del producto | Migración: pipelines que la usaban quedan inválidos hasta reeditar (bloqueados al publicar/ejecutar) |

#### Relación con el menú de apps

| Menú / app de producto | Pipeline Step Catalog |
|------------------------|------------------------|
| “¿Puedo usar File Clean como proyecto?” | “¿Puedo poner Clean como **paso** de un flujo?” |
| Se gestiona en APP_FACTORY + `project_kind` | Se gestiona aquí + registro runtime |
| Una app puede existir **solo** en menú | Hasta el checklist §5.1 no es paso |

**MVP del catálogo:** subset fijo (p. ej. Clean, Gate, Split/Merge, Pipe) hardcodeado/config; ampliar entradas sin cambiar el orquestador.

---

## 6. Definición de pipeline (producto)

### Datos mínimos

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| Nombre / código (slug) | Sí | Único por compañía |
| Descripción | No | |
| Pasos ordenados | Sí | ≥1 en MVP; ≥2 para aportar valor real |
| Política global `on_error` | Sí | Default `stop` |
| Visibilidad | Sí | Privado / compañía (alineado a proyectos) |
| Versiones | Sí | Borrador → publicar (como apps) |

### Ciclo de vida (propuesta)

```text
Borrador (editar pasos)
  → Validar (proyectos existen, kinds coherentes, handoffs tipados)
  → Publicar vN
  → Ejecutar solo vN publicada
  → Nuevo borrador vN+1 (copia)
```

### Seguridad y autorizaciones (mismo esquema de la plataforma)

**Principio:** los pipelines viven bajo el **mismo modelo de seguridad** que el resto de DynamicWorkspace: `Company` (tenant), usuarios UF, roles de membresía **PA / ED / GE / CO**, visibilidad privado/compañía, y (si aplica) feature flags / paquete comercial. **Solo quien esté autorizado** puede aplicar cada acción sobre el pipeline.

| Capa | Regla |
|------|--------|
| **Tenant** | Un pipeline pertenece a una `Company`; no se ve ni se ejecuta cruzando compañías |
| **Membresía / rol** | Acciones condicionadas al rol del usuario en el contexto del pipeline (o rol de plataforma equivalente) |
| **Visibilidad** | `members_only` (privado) vs `company` (consulta UF de la compañía) — mismo patrón que proyectos Gate/Clean/SM |
| **Versión publicada** | Ejecutar productivo = solo definición publicada; editar borrador ≠ ejecutar |
| **API / Watch / Scheduler** | La identidad de máquina o el job de sistema actúa **en nombre de la compañía** con scopes; no bypasea tenancy |
| **Pasos → proyectos** | Además del permiso sobre el **pipeline**, el actor debe poder usar los **proyectos referenciados** en cada paso (misma compañía; rol suficiente para ejecutar ese `kind`) |

#### Matriz de acciones (propuesta, paridad PA/ED/GE/CO)

| Acción | PA | ED | GE | CO | Notas |
|--------|----|----|----|-----|--------|
| Listar / ver definición (metadatos) | ✓ | ✓ | ✓ | ✓ | CO: solo lectura; público compañía = consulta sin ser “dueño” |
| Crear pipeline | ✓ | ✓* | — | — | \*Confirmar paridad Clean/Gate |
| Editar borrador / reordenar pasos | ✓ | ✓ | — | — | |
| Publicar versión | ✓ | ✓* | — | — | |
| Gestionar miembros del pipeline (si tiene membresía propia) | ✓ | — | — | — | O heredar permisos de proyecto “contenedor” — decidir en implementación |
| Ejecutar run (UI) | ✓ | ✓ | ✓ | — | |
| Ver runs / auditoría / descargas según TTL | ✓ | ✓ | ✓ | ✓** | \*\*CO: metadatos; sin descarga de contenido si la política de apps lo exige |
| Cancelar run propio / en curso | ✓ | ✓ | ✓* | — | \*Solo propios o según política PA |
| Disparar vía API | Credencial de compañía con scope `pipeline:run` (y proyectos destino) | | | | No es rol UI; es cliente de máquina autorizado |
| Watch / Scheduler enlazado | Watch: PA/ED del contexto. Scheduler: **crear plan** solo **US** PA/ED de la compañía; configurar el plan = PA/ED de membresía. Run auditado `trigger_source=watch\|scheduler` | | | | |

#### Comprobaciones en cada acción

1. Usuario/API autenticado y con seguridad completa (UF / cliente válido).  
2. Pipeline de la **misma Company**.  
3. Rol o scope suficiente para la **acción** (tabla arriba).  
4. Si la acción es **ejecutar**: versión publicada existe; el actor puede ejecutar **cada** proyecto de los pasos (o se deniega el run completo).  
5. Auditoría §7.1 registra actor + `trigger_source` (no hay ejecución anónima).

**No:** roles nuevos inventados solo para Pipeline. **Sí:** reutilizar el paquete de permisos de plataforma ([`docs/security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md)) y el mapa PA/ED/GE/CO de los verticales de archivo.

---

## 7. Pipeline run — informe OK / Error

### Vista de resultado (concepto UI)

```text
Pipeline: nomina-diaria · v3 · COMPLETED|FAILED
Entrada:  nomina_2026_08_12.csv  sha256:…

┌────────┬──────────────┬───────────┬────────────────────────────┐
│ Paso   │ App          │ Estado    │ Detalle                    │
├────────┼──────────────┼───────────┼────────────────────────────┤
│ 1      │ Clean        │ OK        │ job … · 12 reglas · out #1 │
│ 2      │ Merge        │ OK        │ job … · 3 archivos → 1     │
│ 3      │ Gate         │ ERROR     │ 42 filas · code=date_fmt   │
│ 4      │ Pipe         │ SKIPPED   │ stop on error              │
└────────┴──────────────┴───────────┴────────────────────────────┘

Artifacts: [descargar salida paso 1] [informe Gate] …
```

### Contrato lógico de respuesta (API / UI)

```json
{
  "pipeline_run_id": "…",
  "pipeline_version": 3,
  "status": "failed",
  "steps": [
    {
      "step_id": "s1",
      "kind": "file_clean",
      "status": "completed",
      "app_job_id": "…",
      "error_code": null,
      "user_message": null,
      "artifacts": [{ "role": "output", "ref": "…" }]
    },
    {
      "step_id": "s3",
      "kind": "file_gate",
      "status": "failed",
      "app_job_id": "…",
      "error_code": "validation_content",
      "user_message": "El archivo no cumple el contrato publicado.",
      "artifacts": [{ "role": "report", "ref": "…" }]
    }
  ]
}
```

Códigos y mensajes: alinear a [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) por app; el Pipeline agrega códigos propios (`pipeline_invalid`, `pipeline_handoff`, `pipeline_step_failed`, …).

---

## 7.1 Auditoría y log (obligatorio en el diseño)

La auditoría del Pipeline cubre **dos planos**: ciclo de vida de la **definición** y cada **ejecución (run)** con desglose por **paso**. Sin esto no hay compliance ni diagnóstico E2E.

### A) Auditoría de la definición (quién diseñó / cambió)

| Evento | Qué registrar |
|--------|----------------|
| Creación del pipeline | `created_by` (user), `created_at`, compañía |
| Edición de borrador | `updated_by`, `updated_at`, resumen de cambio (opcional diff de pasos) |
| Publicación vN | `published_by`, `published_at`, `version_number`, hash/snapshot de pasos |
| Cambio de visibilidad / archivado | actor + timestamp + valor anterior/nuevo |

> Paridad con publicar en Clean/Gate/Split: la versión publicada es inmutable; el run siempre apunta a esa versión (no al borrador vivo).

### B) Auditoría del disparo (quién / qué activó el run)

Todo `PipelineRun` debe registrar el **canal** y el **actor**:

| `trigger_source` | Significado | Actor típico a guardar |
|------------------|-------------|-------------------------|
| `ui` | Pedido manual desde la pantalla Ejecutar | `triggered_by_user_id` (+ username) |
| `api` | Pedido PLATFORM_API | `triggered_by_api_client_id` / API key id · `idempotency_key` |
| `watch` | Llegada de archivo (File Watch) | `watch_source_id` · path/nombre remoto · `triggered_by` = sistema/watch |
| `scheduler` | Proceso planificado (File Scheduler) | `schedule_id` · cron expression / ventana · `triggered_by` = sistema/scheduler |
| `dependency` | “Tras terminar otro run/job” (fase Scheduler) | `parent_pipeline_run_id` o `parent_job_id` |

Campos mínimos del run (además de status):

| Campo | Uso |
|-------|-----|
| `pipeline_run_id` | Identificador único del run |
| `pipeline_definition_id` + `pipeline_version_number` | Qué definición/versión se ejecutó |
| `trigger_source` | `ui` \| `api` \| `watch` \| `scheduler` \| `dependency` |
| `triggered_by_user_id` / `triggered_by_api_client_id` | Quién o qué máquina |
| `triggered_at` · `started_at` · `finished_at` | Línea de tiempo |
| `duration_ms` | Duración total |
| `company_id` | Tenancy |
| `input_filenames[]` · `input_sha256[]` | Evidencia de entrada |
| `idempotency_key` | Si vino de API (evitar dobles) |
| `client_ip` / `user_agent` | Opcional MVP; recomendable en API |
| `correlation_id` | Trazas entre API ↔ orquestador ↔ jobs de app |
| `dry_run` | Si fue vista previa |

### C) Auditoría por paso (cómo terminó cada eslabón)

Cada `PipelineStepRun`:

| Campo | Uso |
|-------|-----|
| `step_id` · `order` · `label` | Identidad del paso en el snapshot |
| `kind` · `project_id` · `published_version_number` | Qué app/proyecto/versión se invocó |
| `status` | `pending` · `running` · `completed` · `failed` · `skipped` |
| `started_at` · `finished_at` · `duration_ms` | Timing del paso |
| `app_job_id` | FK/link al job nativo (CleanJob, Gate job, SplitMergeJob, …) |
| `error_code` · `user_message` | Si falló (catálogo UI_MESSAGES + pipeline_*) |
| `metrics` (JSON) | Resumen: filas leídas, partes, etc. (de la app) |
| `artifacts[]` | refs + roles (`input`, `output`, `report`, `zip`) + hashes |
| `skip_reason` | p. ej. `stop_on_error` tras fallo del paso anterior |

**Regla:** el log del Pipeline **no sustituye** el historial de cada app; lo **enlaza** vía `app_job_id`. Detalle fino (reglas aplicadas celda a celda) sigue en el job de la app.

### D) Otros valores de auditoría / log importantes

| Tema | Qué guardar / decidir |
|------|------------------------|
| **Veredicto global** | `status` del run + `failed_step_id` (primer fallo si `on_error=stop`) |
| **Política aplicada** | `on_error` efectivo del run (del snapshot) |
| **Snapshot de pasos** | Copia inmutable usada (no “lo que hay hoy en borrador”) |
| **Notificaciones** | Si se envió correo/webhook: destinatario, resultado, timestamp |
| **Reintentos** | `attempt` / `retry_of_run_id` (Watch/Scheduler/API) |
| **Cancelación** | `cancelled_by`, `cancelled_at` si aplica |
| **Retención** | TTL de artifacts del run (alineado a apps; Archive puede custodiar más tiempo) |
| **PII** | No loguear contenido de celdas en el orquestador; solo metadatos/hashes |
| **Append-only** | Eventos de auditoría no se editan; borrado de run = soft + política PA |

### E) Eventos sugeridos (timeline del run)

```text
pipeline_run.created
pipeline_run.started
pipeline_step.started   (step_id)
pipeline_step.completed | failed | skipped
pipeline_run.completed | failed | cancelled
pipeline_run.notify_sent   (opcional)
```

Útil para UI de detalle, webhooks PLATFORM_API y futura alimentación de [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md).

### F) Ejemplo de registro de auditoría (run)

```text
pipeline_run_id: 9f3a…
pipeline: nomina-diaria  v3
trigger_source: scheduler
schedule_id: sch_nomina_0200
triggered_by: system:scheduler
triggered_at: 2026-08-12 02:00:01Z
input: nomina_2026_08_12.csv  sha256:abc…
status: failed  (failed_step=s3)

  s1 file_clean  completed  1.2s  app_job=…  out sha256:def…
  s2 file_merge  completed  3.4s  app_job=…  out sha256:ghi…
  s3 file_gate   failed     0.8s  app_job=…  error_code=validation_content
  s4 dms         skipped    —     reason=stop_on_error
```

Otro disparo del mismo pipeline:

```text
trigger_source: api
triggered_by_api_client_id: client_erp_01
idempotency_key: erp-2026-08-12-001
correlation_id: …
```

```text
trigger_source: ui
triggered_by_user_id: 42 (jperez)
```

---

## 8. Handoff entre pasos (crítico)

| Transición | Regla MVP |
|------------|-----------|
| 1 archivo → 1 archivo (Clean→Gate, Clean→Pipe) | Salida `output` del previo = entrada del siguiente |
| Merge → Gate/Pipe | Salida consolidada única |
| Split → ? | **Decisión de producto:** (A) fan-out: N sub-runs del siguiente kind por parte; (B) solo ZIP como artifact final y fin de cadena; (C) paso “foreach” explícito. **MVP recomienda (B) o (C) explícito — no fan-out implícito.** |
| → Match | Requiere **dos** entradas: definir `input_A` / `input_B` (artifact de pasos previos o upload secundario) |
| Profiler / Scout en medio | Pueden ser pasos “side” (`produces_file: false`): no cambian el archivo; el handoff sigue el último artifact de datos |

Sin handoff tipado válido → **no publicar** el pipeline (validación en diseño).

---

## 9. Ejemplos de negocio

### EJ-01 — Clean → Gate (mínimo útil)

```text
[1] file_clean   proyecto clean-nomina     (publicado)
[2] file_gate    proyecto gate-nomina      (publicado)
on_error: stop
```

**Entrada:** CSV crudo del proveedor.  
**Éxito:** Gate ACCEPTED + artifacts.  
**Fallo típico:** paso 2 ERROR con informe; paso 1 OK; operador abre Repair (futuro) o corrige fuente.

### EJ-02 — Clean → Merge → Gate

```text
[1] file_clean   clean-extractos
[2] file_merge   sm-trimestre          ← input_from: pipeline_input (N archivos) 
                                       ← o: varios uploads en el run
[3] file_gate    gate-extracto-unificado
```

**Nota:** Merge como paso 1 o 2 exige que el **run** acepte múltiples archivos de entrada al pipeline; Clean previo puede aplicarse **por archivo** (fan-in Clean × N → Merge) — fase 2 si complica el MVP.

**Variante MVP más simple:**

```text
Usuario ya tiene 3 CSV limpios
[1] file_merge   sm-trimestre
[2] file_gate    gate-extracto
```

### EJ-03 — Split → Gate por partes (fase 2 / foreach)

```text
[1] file_split   sm-nomina-por-sucursal
[2] foreach part → file_gate  gate-nomina
```

MVP puede posponer foreach y documentarlo como extensión.

### EJ-04 — Clean → Gate → Pipe → Match

```text
[1] file_clean   clean-ventas
[2] file_gate    gate-ventas
[3] dms          pipe-ventas-erp
[4] file_match   match-ventas-vs-erp
    options: { "input_A": "step:s3.output", "input_B": "pipeline_input:erp_extract" }
```

**Veredicto global:** FAILED si Match reporta mismatches según umbral (definir si Match `completed` con diferencias = OK de job o failed de pipeline — política de producto).

### EJ-05 — Disparo por Watch + informe

```text
Watch: SFTP drop extracto_*.csv
  → pipeline_id = extracto-diario v5
  → steps Clean → Gate → Pipe
  → Notify correo si pipeline_run.status = failed
```

### EJ-06 — PLATFORM_API consume Pipeline

```http
POST /api/v1/pipelines/{pipeline_id}/runs
Authorization: Bearer …
Idempotency-Key: …
Content-Type: multipart/form-data

file: nomina.csv
```

Respuesta async `202` + `pipeline_run_id`; polling de estado con desglose por paso (§7).  
Equivalente: `kind=file_pipeline` en el contrato unificado de PLATFORM_API.

---

## 10. Pantallas (visión UX)

| Pantalla | Contenido |
|----------|-----------|
| Listado de pipelines | Código, **estado**, versión (columna), **pasos** (máx. 2 visibles + `...` verde si hay más), último run. Filtros: búsqueda y estado |
| Diseñador | Canvas o lista ordenable de pasos; picker de proyecto por kind; validación handoff |
| Publicar | Checklist; si Diseñar no está completo, el botón no publica y avisa pasos pendientes |
| Ejecutar | Upload entrada(s); dry-run opcional; progreso por paso |
| Detalle de run | Tabla §7 + **auditoría de disparo** (§7.1) + enlaces a jobs de cada app + descargas |
| Historial / auditoría | Filtros: trigger_source, usuario, API client, schedule, fechas, status |
| Ayuda | Copy: orquestación, no “nuevo ETL” |

Formularios HTML plano; servicios con `ok` / `error_code` / `user_message` ([`UI_MESSAGES.md`](definition_app/UI_MESSAGES.md)).

---

## 11. Modelo conceptual (persistencia — borrador)

```text
Company
  └── PipelineDefinition (slug, status: active|in_progress|inactive,
                            visibility, created_by, created_at, …)
        ├── PipelineVersion (draft | published, snapshot JSON,
        │                    published_by, published_at, version_number)
        ├── PipelineAuditEvent (definition-level: create/update/publish/…)  [opcional tabla o log]
        └── PipelineRun (
              version FK, status,
              trigger_source: ui|api|watch|scheduler|dependency,
              triggered_by_user_id | triggered_by_api_client_id,
              schedule_id?, watch_source_id?, parent_run_id?,
              idempotency_key?, correlation_id?,
              triggered_at, started_at, finished_at, duration_ms,
              input_filenames, input_sha256, dry_run, …
            )
              └── PipelineStepRun (
                    step_id, kind, project_id, published_version_number,
                    status, started_at, finished_at, duration_ms,
                    app_job_id, error_code, user_message,
                    metrics JSON, artifacts JSON, skip_reason?
                  )
```

- El **snapshot** de pasos se congela al publicar (como `sm_rules` / Clean).  
- `app_job_id` apunta al job nativo (`CleanJob`, `SplitMergeJob`, `DmsExecutionJob`, …).  
- Storage: reutilizar `storage_service` / raíces por run de pipeline.  
- Auditoría detallada: §7.1 (definición + disparo + paso).

---

## 12. Validaciones al publicar / ejecutar

| Check | Rechazo si… |
|-------|-------------|
| Diseñar incompleto (paso 1 del hub) | No hay rail guardado con ≥1 paso válido: **no publicar**. UI: alerta *No puede publicar. Pasos no completados: Diseñar pasos.* |
| Paso sin proyecto | Proyecto inexistente o otra compañía |
| Kind desconocido / no habilitado | `kind` no está en el Pipeline Step Catalog o `pipeline_enabled=false` |
| Kind ≠ project_kind | Incoherencia |
| Sin versión publicada | Proyecto del paso sin `current_version` |
| Handoff imposible | p. ej. Match sin dos entradas definidas |
| Ciclo / orden | `order` duplicado o `input_from` a paso futuro |
| Permisos | Usuario/máquina sin derecho a ejecutar alguno de los proyectos |
| Definición no operativa | `status` distinto de `active`, o `active` sin versión publicada: rechazar disparo (UI/API/Watch/Scheduler) |

---

## 13. Fases de implementación sugeridas

### Fase A — MVP (diseño + run lineal) — **hecho**

- CRUD pipeline + publicar.  
- Pasos: Clean, Gate, Split **o** Merge, Pipe (los que tengan runner estable).  
- `on_error=stop`; handoff 1→1.  
- UI ejecutar + detalle de run.  
- Encadenamiento **sin** re-upload manual (artifact refs).

### Fase B — Disparadores — **hecho**

- Watch → `pipeline_id`.  
- Scheduler → `pipeline_id`.  
- PLATFORM_API `mode=pipeline` / `kind=file_pipeline`.  
- Notificaciones en fallo global.

### Fase C — Potencia

- Foreach / fan-out post-Split.  
- `on_error=continue` / branches.  
- Match / Repair / Profiler como pasos de primera clase.  
- Integración Archive (expediente = pipeline_run).  
- Schema Registry en resolución de contratos.

> **Orden de programa:** Fase A+B cerradas en `main`. Fase C no bloquea el MVP. Archive / Registry siguen previstos.

---

## 14. ¿Es algo funcional?

| Pregunta | Respuesta |
|----------|-----------|
| ¿Hace trabajo real? | **Sí** — orquesta motores reales de cada app |
| ¿Reemplaza las apps? | **No** — las compone |
| ¿Útil sin Watch/API? | **Sí** — ya con UI (adiós upload entre apps) |
| ¿PLATFORM_API lo consume? | **Sí** — `kind=file_pipeline` / atajo de runs |
| ¿Sustituye Archive? | **No** — Archive custodia; Pipeline ejecuta |

---

## 15. Criterio de aceptación (MVP cerrado)

1. ¿Cada paso reutiliza el runner de la app sin fork?  
2. ¿Solo versiones publicadas en run productivo?  
3. ¿Informe por paso + global con `error_code` alineados?  
4. ¿Auditoría §7.1: creador/publicador, `trigger_source`, actor, timing, hashes, `app_job_id` por paso?  
5. ¿Handoff tipado validado al publicar?  
6. ¿Catálogo de pasos (§5.1) opt-in — nueva app no entra sola; checklist de incorporación?  
7. ¿Política `stop` clara en MVP?  
8. ¿Contrato con PLATFORM_API documentado (`mode=pipeline`)?  
9. ¿MVP lineal sin foreach implícito post-Split?  
10. ¿Tenancy Company + matriz PA/ED/GE/CO + permiso también sobre proyectos de cada paso?  
11. ¿API/Watch/Scheduler sin bypassear el mismo esquema de autorización?

---

## 16. Próximos pasos de diseño

1. Mantener este archivo como **paraguas FILE_PIPELINE**.  
2. Revisar con producto los ejemplos EJ-01…EJ-06 y la política Split→siguiente.  
3. Specs por módulo: [`definition_app_FILE_PIPELINE/`](definition_app_FILE_PIPELINE/) (esqueleto + prototipos). Implementar Django solo con «Desarrolla el módulo».  
4. [`PLATFORM_API.md`](PLATFORM_API.md) ya cubre `kind=file_pipeline`, `wait`, auditoría HTTP §10.2 y dashboard §10.3; no duplicar §7.1 allí.  
5. Actualizar [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §15 como puntero a este doc (visión → producto).  
6. Spike técnico: pasar `artifact_ref` entre runners; implementar **Pipeline Step Catalog** (config/código) con subset MVP.  
   **Alcance de la mejora (todas las apps ejecutables):** el runner acepta referencia (`artifact_ref`, hash, objeto en storage), no solo upload de `<input type="file">`. La UI Ejecutar **se conserva**. IFS/SFTP/cloud **no** se configuran en File Gate ni en cada vertical — [`FILE_WATCH.md`](FILE_WATCH.md) y [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md).  
7. Al nacer cada app nueva: checklist §5.1 antes de marcar `pipeline_enabled=true`.

---

## 17. Glosario

| Término | Definición |
|---------|------------|
| **FILE_PIPELINE** | Orquestador de flujos multi-app |
| **definition status** | Ciclo de vida del pipeline: `active` (Activo) · `in_progress` (En proceso) · `inactive` (Inactivo) |
| **Pipeline run** | Ejecución auditable de una versión + entradas + disparo (§7.1) |
| **Step run** | Resultado de un eslabón (OK/ERROR + job de app + timing) |
| **trigger_source** | Canal de activación: `ui` · `api` · `watch` · `scheduler` · `dependency` |
| **correlation_id** | Id de traza entre API, orquestador y jobs de app |
| **Pipeline Step Catalog** | Registro de `kind` habilitados como paso (opt-in; mantenimiento al crear apps) |
| **pipeline_enabled** | Flag: la app existe pero puede no estar disponible en el diseñador |
| **Handoff** | Paso de artifacts entre steps |
| **Job encadenable** | Visión FILE_OPS; este doc es su producto |
| **mode=pipeline** | Cómo PLATFORM_API invoca una cadena completa |
| **Fan-out / foreach** | Ejecutar el siguiente kind por cada parte Split (fase 2) |

---

## 18. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY.md`](APP_FACTORY.md) | Visión fábrica; prioridad plataforma |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | §15 Job encadenable → **este doc** |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Apps §2 como pasos |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Disparador HTTP; **puede consumir Pipeline** |
| [`FILE_WATCH.md`](FILE_WATCH.md) | Disparo por llegada → pipeline_id |
| [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) | Disparo por tiempo/dependencia → pipeline_id; `trigger_source=scheduler`; detalle de schedule en FILE_SCHEDULER §7–§8 |
| [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md) | Custodia E2E del pipeline_run |
| [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) | Contratos compartidos (fase C) |
| [`FILE_CLEAN.md`](FILE_CLEAN.md) · [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · [`FILE_GATE.md`](FILE_GATE.md) · … | Pasos concretos |
| [`FILE_REPAIR.md`](FILE_REPAIR.md) · [`DATA_PROFILER.md`](DATA_PROFILER.md) | Pasos futuros / bajo revisión |
| [`definition_app_FILE_PIPELINE/`](definition_app_FILE_PIPELINE/) | Specs por módulo (este producto) |
| [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | Códigos de error |
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Índice de producto |

---

*Documento vivo. Base de un desarrollo global de orquestación; no implementar hasta OK explícito de producto y spike de handoff.*
