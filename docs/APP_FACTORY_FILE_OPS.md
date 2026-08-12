# APP FACTORY — Operaciones de archivo (alrededor del pipeline)

> **Nombre mnemotécnico:** `FILE_OPS`  
> Alias: *Ops de archivo* · *Alrededor del procesamiento* · *Pipeline ops*  
> Archivo: [`docs/APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md)  
> Origen: propuestas de producto (`propuestas.txt`) + análisis frente a la suite actual  
> Padres: [`APP_FACTORY.md`](APP_FACTORY.md) · hermano de [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md)

---

## 0. Para qué sirve este documento

### Qué es

Paraguas de producto de la **siguiente oleada** de capacidades de archivo: lo que ocurre **antes, después y alrededor** de modelar → validar → transformar → emitir → conciliar. No es código ni manual de usuario.

### Qué función cumple

| Función | Descripción |
|---------|-------------|
| **Capturar ideas** | Registrar propuestas sin perder el hilo respecto a la suite ya entregada |
| **Delimitar** | Separar app nueva vs módulo vs capa de plataforma; evitar duplicar FilePipe / File Gate |
| **Priorizar** | MVP ampliado accionable (qué sí / qué no ahora) |
| **Preparar specs** | Cuando se priorice un vertical, extraer `FILE_*.md` + `definition_app_*` |

### Alcance de *este* documento (sí / no)

| Sí | No |
|----|-----|
| Propuestas de Clean, Split, Merge, Repair, Profiler, Watch, Scheduler, Archive, Schema Registry | Reescribir Gate / Pipe / Reverse / Match / Scout (ya tienen docs) · Diff como app aparte (cubierto por Match) |
| Fronteras conceptuales y reuso del chasis + motor DMS | Specs de pantalla paso a paso |
| Arquitectura en capas / pipeline encadenable | Roadmap CRM / formularios (§3 APP_FACTORY) |
| Decisión de no crear **File Convert** como app | Implementación Django |

### Relación con la familia §2 (HIGH_REUSE)

| Documento | Rol |
|-----------|-----|
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Verticales **hechos / en curso** sobre el motor DMS (Gate, Reverse, Match, Scout, Seed, Catalog) |
| **Este doc (`FILE_OPS`)** | Huecos **alrededor** de esos verticales + orquestación |

```text
§2 HIGH_REUSE (núcleo de producto archivo)
  Scout → Gate → Pipe / Reverse → Match (+ Seed, Catalog)

FILE_OPS (esta oleada)
  Profiler · Clean · Repair · Split/Merge
  Watch · Scheduler · Archive · Schema Registry
  (Diff técnico → no app; usar File Match)

Disparador HTTP (plataforma, no app de menú)
  PLATFORM API — ver [`PLATFORM_API.md`](PLATFORM_API.md)
```
---

## 1. Resumen ejecutivo

### Idea central

La arquitectura actual cubre bien:

```text
modelar → validar → transformar → generar → conciliar
```

No conviene agregar apps que **repitan** FilePipe o File Gate. Sí conviene cubrir huecos:

| Momento | Hueco | Propuestas |
|---------|-------|------------|
| **Antes** | Datos sucios / desconocidos / sin perfil estadístico | Clean, Profiler, Scout (ya existe) |
| **Durante** | Partir / unir / reparar | Split, Merge, Repair |
| **Comparar A vs B** | Cuadrar / ver diferencias por clave | **File Match** (ya entregado; no File Diff) |
| **Después** | Custodia E2E | Archive |
| **Alrededor** | Automatización y contratos compartidos | Watch, Scheduler, Schema Registry |

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Muchos fallos no son “esquema incorrecto”, sino datos sucios, lotes enormes, cambios entre versiones o procesos 100 % manuales (upload → ejecutar) |
| **Solución** | Capas reutilizables (reglas, jobs, parsers) empaquetadas como apps o módulos con propósito claro |
| **Beneficio** | Pipelines sin código, con versiones, permisos y auditoría de extremo a extremo |
| **Audiencia** | Operaciones, integración, calidad de datos, tesorería / nómina / ERP |

### Inventario (estado mixto)

| Aplicativo | Nemotécnico | Tipo | Diferenciador en una frase |
|------------|-------------|------|----------------------------|
| **File Clean** | `FILE_CLEAN` | App / paso pre-Gate · **hecho** | Limpia y normaliza **antes** de validar o transformar |
| **File Split** | `FILE_SPLIT` | Utilidad dual · **en definición** | Parte un archivo grande según reglas — [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) |
| **File Merge** | `FILE_MERGE` | Utilidad dual · **en definición** | Consolida varios archivos en uno — mismo doc |
| **File Convert** | — | **No app** | Conversiones triviales → modo simple en **FilePipe** |
| **File Diff** | — | **No app** | Antes/después y diferencias → **File Match** (clave + compare) |
| **File Repair** | `FILE_REPAIR` | App / modo Gate | Corrige con trazabilidad a partir de rechazos Gate |
| **File Watch** | `FILE_WATCH` | Plataforma | Ingestión automática (carpeta / SFTP / API…) |
| **File Scheduler** | `FILE_SCHEDULER` | Plataforma | Cron / dependencias entre jobs |
| **File Archive** | `FILE_ARCHIVE` | Plataforma | Custodia E2E entrada → salida + hashes |
| **Data Profiler** | `DATA_PROFILER` | App | Calidad y estadística del **contenido** (≠ Scout) |
| **Schema Registry** | `SCHEMA_REGISTRY` | Plataforma | Contratos versionados compartidos entre apps |

---

## 2. Arquitectura en capas (visión)

```text
                 STRUCTURE SCOUT
                       ↓
                 DATA PROFILER
                       ↓
                   FILE CLEAN
                       ↓
                   FILE GATE
             ┌─────────┴─────────┐
             ↓                   ↓
         FILEPIPE          REVERSE STUDIO
             └─────────┬─────────┘
                       ↓
                  FILE MATCH
                       ↓
                 FILE ARCHIVE
```

Herramientas transversales:

```text
FILE SPLIT  ←→  FILE MERGE
       (conversión simple → FilePipe, no app aparte)
       (diff / antes-después → File Match, no app aparte)
```

Orquestación:

```text
FILE WATCH → FILE SCHEDULER → jobs automáticos → notificar
PLATFORM API (HTTP) → mismo runner de Job → notificar
```

Detalle de contrato y ejemplos: [`PLATFORM_API.md`](PLATFORM_API.md).

Cada bloque puede ser app o módulo, pero el usuario debería poder **encadenarlos** bajo un concepto común de **Job** (archivo + versión + resultado + auditoría).

---

## 3. Fronteras críticas (no confundir)

| Concepto A | Concepto B | Diferencia |
|------------|------------|------------|
| **File Gate** | **File Clean** | Gate = ¿cumple el contrato? · Clean = arreglar / normalizar datos |
| **File Gate** | **File Repair** | Gate = informe de rechazo · Repair = aplicar correcciones **auditadas** y reintentar |
| **FilePipe** | **File Convert** | Pipe = mapeo + reglas de negocio · Convert trivial = solo cambiar formato (queda en Pipe) |
| **File Match** | **File Diff (retirado)** | Match cubre A vs B por clave (incl. antes/después). No se abre app Diff aparte. |
| **Structure Scout** | **Data Profiler** | Scout = ¿qué estructura parece? · Profiler = ¿cómo son los datos (nulos, uniques, outliers)? |
| **Profile Seed** | **Schema Registry** | Seed = clonar estructura a un proyecto · Registry = catálogo central de contratos versionados |
| **Historial por app** | **File Archive** | Historial local del vertical · Archive = custodia unificada del pipeline E2E |
| **Upload manual** | **File Watch** | Usuario sube · Watch detecta llegada y dispara pipeline |
| **UI / Watch / Scheduler** | **PLATFORM API** | Mismo Job; disparador HTTP — [`PLATFORM_API.md`](PLATFORM_API.md) |

---

## 4. FILE CLEAN — Limpieza y normalización

### 4.0 Qué es y qué hace

Complemento natural de File Gate: recibe un archivo y aplica **reglas de limpieza** antes de validar o transformar.

Ejemplos de reglas: trim / caracteres invisibles, mayúsculas-minúsculas, fechas, separadores decimales, duplicados, teléfonos/documentos, replace de valores, vacíos/null, encoding, BOM.

### 4.1 Flujo típico

```text
Archivo → File Clean → File Gate → FilePipe
Archivo → File Clean → File Match
```

### 4.2 Reutilización

| Pieza | Uso |
|-------|-----|
| Parsers / intake DMS | Lectura |
| Motor de **reglas** FilePipe (trim, case, date_format, replace_map…) | Núcleo |
| Versionado + historial de job | Mismo patrón que Gate/Pipe |
| Bridge Gate | Opcional: Clean → Gate en cadena |

### 4.3 Alcance MVP (borrador)

| Incluye | Excluye |
|---------|---------|
| Catálogo de reglas de limpieza versionado | “IA que adivina” sin regla explícita |
| Preview antes/después + descarga limpia | Sustituir el mapeo de negocio de FilePipe |
| Encadenar a Gate / Match | Editor de layout posicional completo |

### 4.4 Riesgo

Duplicar la UI de reglas de FilePipe. Mitigación: **motor de reglas compartido**; Clean es el *skin* “pre-calidad”, no un segundo ETL.

### 4.5 Criterio APP_FACTORY

Alto reuso · diferenciador claro (antes de Gate) · MVP acotable · **prioridad ⭐⭐⭐⭐⭐**.

**Definición de producto:** [`FILE_CLEAN.md`](FILE_CLEAN.md) · specs [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/).

---

## 5. FILE SPLIT — Dividir archivos

### 5.0 Qué es y qué hace

Parte un archivo grande según reglas (máx. filas, valor de columna, rango de fechas, compañía/sucursal, tamaño máximo).

```text
nomina.xlsx → File Split → empleados_activos.csv, empleados_bogota.csv, …
```

### 5.1 Reutilización

Parsers + serializadores DMS; jobs + descarga múltiple; roles PA/GE.

### 5.2 Frontera

No es FilePipe (no mapea a un esquema destino de negocio). Es **partición**.

### 5.3 Criterio

Alto valor operativo · poco solape · **prioridad ⭐⭐⭐⭐** (junto con Merge).

**Definición de producto:** [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · specs [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/).

---

## 6. FILE MERGE — Consolidación

### 6.0 Qué es y qué hace

Inverso de Split: append, unión por columnas, combinación por clave, homologación ligera, control de columnas faltantes, deduplicación opcional.

```text
enero.xlsx + febrero.xlsx + marzo.xlsx → File Merge → Q1.xlsx
```

Relación interesante (fase 2): `múltiples archivos → Merge → Worksheet`.

### 6.1 Reutilización

Parsers/serializers; opcionalmente carga a Records (fase 2).

### 6.2 Frontera

Merge de **archivos** ≠ conciliador Match (Match compara y reporta; Merge produce un archivo consolidado).

### 6.3 Criterio

**Prioridad ⭐⭐⭐⭐** con Split. Carga a Worksheet = fase posterior.

**Definición de producto:** [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · specs [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/).

---

## 7. FILE CONVERT — No como aplicación

Aunque FilePipe puede cubrir conversiones, una app “solo cambia formato” (CSV↔Excel↔JSON…) **duplicaría producto**.

| Caso | Dónde |
|------|--------|
| “Convierte este CSV a JSON” | **Modo / plantilla simple en FilePipe** (mapeo 1:1) |
| “Renombra campos, fechas, lookups y genera JSON del ERP” | **FilePipe** completo |

**Decisión:** no abrir `project_kind` ni menú File Convert en esta oleada.

---

## 8. FILE DIFF — No como aplicación

Una app “solo diff técnico entre v1 y v2” **no aporta valor agregado** frente a **File Match**, que ya cruza dos archivos por clave y reporta matched / only_A / only_B / mismatch (incl. auditoría antes/después del mismo reporte).

| Caso | Dónde |
|------|--------|
| “¿Cuadran extracto vs ERP?” | **File Match** |
| “¿Qué cambió entre exportación de ayer y hoy?” (misma clave de negocio) | **File Match** (perfiles A/B + compare) |
| Diff estructural puro sin clave (encoding, columnas sueltas, git-style) | **Fuera de alcance** de esta oleada; no justifica app aparte |

**Decisión:** no abrir `project_kind` ni menú File Diff. Actualizar inventario y prioridad; ver [`FILE_MATCH.md`](FILE_MATCH.md).

---

## 9. FILE REPAIR — Reparación asistida

### 9.0 Qué es y qué hace

Cuando File Gate rechaza, ofrece **correcciones auditadas** (no silenciosas) y genera un archivo reparado para revalidar.

```text
original → File Repair → repaired → File Gate → ACCEPTED
```

Cada corrección registra: regla, campo, valor original, valor corregido, usuario, fecha, versión.

### 9.1 Reutilización

Informe de errores Gate; motor de reglas (solapa Clean); historial de job.

### 9.2 Frontera

Repair puede ser **modo de Gate** o app hermana. Clean = reglas genéricas a priori; Repair = dirigido por **errores concretos del job**.

### 9.3 Criterio

Alto diferenciador · acoplado a Gate · candidata fuerte tras Clean (o empaquetada con Clean en un solo vertical “calidad”).

---

## 10. FILE WATCH — Recepción automática

### 10.0 Qué es y qué hace

En lugar de solo “Upload → ejecutar”, detecta llegada de archivos y dispara pipeline (Gate → Clean → Pipe → Match → resultado → notificar).

Orígenes posibles: carpeta, SFTP, API, cloud storage, correo, webhook.

### 10.1 Reutilización

Jobs existentes de cada app; notificaciones (Resend); storage Railway/S3.

### 10.2 Coste

Alto en **ops/seguridad** (credenciales, cuotas, idempotencia, reintentos). No es solo UI.

### 10.3 Criterio

Máximo valor de automatización · **prioridad ⭐⭐⭐⭐⭐** de producto, **después** de estabilizar Clean/Split·Merge y el modelo de Job encadenable. Relacionado con §4 APP_FACTORY (bandeja vigilada) y roadmap DMS.

---

## 11. FILE SCHEDULER — Ejecución programada

### 11.0 Qué es y qué hace

Cron / calendarios / dependencias entre jobs (diario 02:00, fin de mes, “después de Job A”).

### 11.1 Frontera con Watch

| Watch | Scheduler |
|-------|-----------|
| Dispara por **llegada** de archivo | Dispara por **tiempo** o dependencia |

### 11.2 Reutilización

Cola + `DmsExecutionJob` / jobs de verticales; no requiere un `project_kind` por formato.

### 11.3 Criterio

Capa de **plataforma** · alinear con “Scheduling DMS Fase 3” en APP_FACTORY · implementar junto o justo después de Watch.

---

## 12. FILE ARCHIVE — Custodia y trazabilidad E2E

### 12.0 Qué es y qué hace

Hoy cada app tiene historial. Archive unifica:

```text
Proceso #84921
Entrada: nomina_2026_08.csv  SHA-256: …
Validación: PASSED (Gate v3)
Transformación: FilePipe v3
Salida: nomina_erp_2026_08.txt
Estado: COMPLETED
```

Responde: *¿Qué archivo produjo exactamente este resultado?*

### 12.1 Criterio

Muy valioso en finanzas/nómina · capa transversal · priorizar cuando haya pipelines multi-app en producción.

---

## 13. DATA PROFILER — Perfil estadístico

### 13.0 Qué es y qué hace

Structure Scout detecta **estructura**. Profiler mide **calidad del contenido** (nulos, uniques, duplicados, longitudes, distribución, outliers, posibles PII, drift vs corridas anteriores).

```text
CLIENTE: 152.430 filas · 1.823 vacíos · 149.221 únicos · …
```

### 13.1 Flujo

```text
Scout → Data Profiler → Clean → Gate → …
```

### 13.2 Criterio

No fusionar con Scout · **prioridad ⭐⭐⭐⭐**.

---

## 14. SCHEMA REGISTRY — Catálogo de contratos

### 14.0 Qué es y qué hace

Repositorio central de contratos versionados (campos, tipos, longitudes, reglas, compatibilidad, propietario, consumidores) consumido por Gate, Pipe, Reverse, Match.

```text
Schema Registry → Gate / Pipe / Reverse / Match
```

### 14.1 Frontera

Hoy los contratos viven **por proyecto**. Registry implica cambio de modelo mental (y eventual migración). Relacionado con Master Catalog (códigos) pero distinto (esquema de archivo vs maestros de negocio).

### 14.2 Criterio

Plataforma · **después** de estabilizar verticales §2 y Clean/Seed · no bloquear el MVP de Clean/Split·Merge.

---

## 15. Job común (visión de orquestación)

```text
Archivo
  → [Detect]      Structure Scout
  → [Profile]     Data Profiler
  → [Clean]       File Clean
  → [Validate]    File Gate
  → [Transform]   FilePipe
  → [Generate]    Reverse Studio
  → [Reconcile]   File Match
  → [Archive]     File Archive
  → [Notify]      correo / webhook
```

Cada paso = app/módulo independiente; el usuario arma **pipelines** sin programar, con versiones, permisos y trazabilidad. El mismo Job puede dispararse desde UI, Watch, Scheduler o **[`PLATFORM_API.md`](PLATFORM_API.md)**.

---

## 16. Prioridad sugerida (MVP ampliado)

| Prioridad | Ítem | Motivo | Forma sugerida |
|-----------|------|--------|----------------|
| ⭐⭐⭐⭐⭐ | **File Clean** | Complementa Gate; reusa reglas DMS | App — [`FILE_CLEAN.md`](FILE_CLEAN.md) · [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/) · **hecho** |
| ⭐⭐⭐⭐⭐ | **File Watch** | De manual a automático | Plataforma (más tarde que Clean) |
| ⭐⭐⭐⭐ | **File Split / Merge** | Operaciones frecuentes | App dual — [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) · **en definición** · rama `feature/file-split-merge` |
| ⭐⭐⭐⭐ | **Data Profiler** | Inteligencia antes de modelar/validar | App hermana de Scout |
| ⭐⭐⭐ | **File Repair** | Diferenciador post-Gate | Modo Gate o app con Clean |
| ⭐⭐⭐ | **File Scheduler** | Cron / dependencias | Plataforma (con Watch) |
| ⭐⭐ | **File Archive** | Custodia E2E | Capa cuando haya cadenas |
| ⭐⭐ | **Schema Registry** | Contratos compartidos | Plataforma |
| — | **File Convert** | Evitar duplicar Pipe | **No app** |
| — | **File Diff** | Cubierto por Match; sin valor agregado aparte | **No app** — [`FILE_MATCH.md`](FILE_MATCH.md) |

**Orden práctico recomendado para empezar:**

1. **File Clean** — **hecho**  
2. **Split/Merge** — **en definición** [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md)  
3. **Data Profiler**  
4. **Repair** (o unificar Clean+Repair)  
5. **Watch + Scheduler**  
6. **Archive / Schema Registry**

---

## 17. Criterio de aceptación (familia FILE_OPS)

Antes de abrir rama `feature/<slug>`:

1. ¿Reutiliza Company + seguridad + billing?  
2. ¿Diferenciador claro frente a FilePipe / File Gate / Match / Scout?  
3. ¿App, módulo de una app existente, o capa de plataforma? (decidir explícito)  
4. ¿MVP &lt; 1 fase con formatos y pantallas acotados?  
5. ¿Motor compartido (reglas / parsers / jobs) documentado para no bifurcar?  
6. ¿Plan de doc hijo (`FILE_CLEAN.md`, etc.) + prototipo antes de modelos?

---

## 18. Próximos pasos de diseño

1. Mantener este archivo como **paraguas FILE_OPS**.  
2. **File Split/Merge (en definición):** [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) + [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) — prototipar e implementar por módulo con OK explícito.  
3. Spike técnico: parsers/serializers DMS para 1→N y N→1 + límites de partes.  
4. Actualizar [`APP_FACTORY.md`](APP_FACTORY.md) §5 / §8 cuando un ítem pase a definición o implementación.  
5. **PLATFORM API:** implementar **al finalizar** las apps FILE_OPS; cada app nace API-ready (`kind` + runner). Ver [`PLATFORM_API.md`](PLATFORM_API.md).  
6. No mezclar estas propuestas en el cuerpo principal de [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) (solo puntero).  
7. **File Diff:** retirado como app (§8); no generar `FILE_DIFF.md` ni `definition_app_FILE_DIFF/`.  
8. **File Clean:** hecho — [`FILE_CLEAN.md`](FILE_CLEAN.md).

---

## 19. Glosario

| Término | Definición |
|---------|------------|
| **FILE_OPS** | Familia de capacidades alrededor del pipeline de archivos |
| **File Clean** | Normalización/limpieza pre-validación o pre-transformación |
| **File Diff** | Propuesta **retirada** — usar File Match |
| **File Repair** | Corrección auditada dirigida por errores de Gate |
| **Data Profiler** | Estadísticas y calidad de contenido |
| **File Watch** | Ingestión por llegada de archivo |
| **File Scheduler** | Disparo por tiempo o dependencia de jobs |
| **File Archive** | Custodia unificada E2E con hashes |
| **Schema Registry** | Catálogo central de contratos de archivo versionados |
| **Job encadenable** | Unidad de ejecución que puede componer pasos de varias apps |
| **PLATFORM API** | Disparador HTTP del Job — ver [`PLATFORM_API.md`](PLATFORM_API.md) |

---

## 20. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY.md`](APP_FACTORY.md) | Visión general y prioridad de fábrica |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Familia §2 (núcleo ya entregado / en curso) |
| [`FILE_CLEAN.md`](FILE_CLEAN.md) | **File Clean** — **hecho** · [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/) |
| [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) | **File Split/Merge** — **en definición** · [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) · rama `feature/file-split-merge` |
| [`PLATFORM_API.md`](PLATFORM_API.md) | API de ejecución remota (**después** de apps FILE_OPS) |
| [`FILE_GATE.md`](FILE_GATE.md) | Validador — hecho |
| [`DataMappingStudio.md`](DataMappingStudio.md) / FilePipe | Motor ETL y reglas |
| [`FILE_MATCH.md`](FILE_MATCH.md) | Conciliador — hecho |
| [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) | Estructura desde muestra — hecho |
| [`REVERSE_STUDIO.md`](REVERSE_STUDIO.md) | Emisor — hecho |
| [`PROFILE_SEED.md`](PROFILE_SEED.md) | Siembra desde definición |
| [`ESTRUCTURA_PROYECTO.md`](ESTRUCTURA_PROYECTO.md) | Convenciones al abrir un vertical |

---

*Documento vivo. Actualizar inventario y §16 cuando una propuesta pase a definición, rama o `main`.*
