# FILE SPLIT / MERGE — Partición y consolidación de archivos

> **Nombre mnemotécnico:** `FILE_SPLIT_MERGE`  
> Alias: *File Split* · *File Merge* · *Utilidad dual de lotes*  
> Archivo: [`docs/FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md)  
> Estado: **definición de producto** · M1–M6 (proyecto → historial) **implementados** (`feature/file-split-merge`)  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §2 (entregado)  
> Specs por módulo: [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/)  
> Estilo: hermano de [`FILE_CLEAN.md`](FILE_CLEAN.md) / [`FILE_MATCH.md`](FILE_MATCH.md)

### Rama de desarrollo y despliegues

| Ítem | Valor |
|------|--------|
| **Rama Git** | `feature/file-split-merge` |
| **Base** | `main` |
| **Despliegues Railway** | Solo desde `main` tras merge del MVP |
| **API pública** | **Después** de las apps FILE_OPS; Split/Merge debe nacer **API-ready** (Job + `kind`) — ver [`PLATFORM_API.md`](PLATFORM_API.md) |

---

## 1. Resumen ejecutivo

**File Split/Merge** es un aplicativo de DynamicWorkspace que permite **partir un archivo en varios** o **consolidar varios archivos en uno**, según reglas versionadas — sin mapear a un esquema de negocio (eso es FilePipe) y sin conciliar por clave (eso es File Match).

```text
Definir cómo se lee el archivo (perfil)
        →
Definir operación: Split (1→N) o Merge (N→1) + reglas
        →
Publicar versión
        →
Subir archivo(s) → preview / ejecutar
        →
Descargar salida(s) + log / métricas
```

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Lotes enormes, un archivo por sucursal/mes, o varios extractos que hay que unir antes de Gate/Pipe/Match — hoy se hacen a mano o con scripts |
| **Solución** | Proyecto reutilizable: perfil de lectura + reglas de partición o consolidación publicadas + job con artifacts |
| **Beneficio** | Menos Excel/scripts; mismos roles, versiones e historial que la suite |
| **Audiencia** | Operaciones, integración, nómina, tesorería, proveedores internos |

### Posicionamiento

| Alternativa | Limitación | Diferenciador Split/Merge |
|-------------|------------|---------------------------|
| FilePipe | ETL de negocio (mapeo destino) | Solo **reparte o une** filas/archivos; no inventa layout de ERP |
| File Match | Compara A vs B e informa | Merge **produce** un archivo; Match **no** une |
| File Clean | Normaliza valores | Clean no parte por sucursal ni une meses |
| Scripts / Power Query | Frágiles, sin roles ni historial | Job auditable + versión publicada |

### Relación con la plataforma

| Pieza | Relación |
|-------|----------|
| Chasis (Company, seguridad, billing, roles) | Reutilizado al 100 % |
| DMS — parsers, serializers, intake | **Núcleo** (lectura y escritura del mismo `file_type`) |
| File Clean / Gate / Pipe / Match | Upstream o downstream típicos (manual en MVP) |
| [`PLATFORM_API.md`](PLATFORM_API.md) | `kind=file_split` / `kind=file_merge` (o un kind con `operation`) cuando exista la API |

---

## 2. Importancia

1. Siguiente prioridad práctica de FILE_OPS tras Clean (Diff retirado → Match).  
2. Alto valor operativo con poco solape de producto.  
3. Reuso fuerte de parsers/serializers ya usados en Clean/Gate/Pipe.  
4. Prepara Jobs homogéneos para Watch / Scheduler / **PLATFORM API**.

---

## 3. Problema que resuelve

### Split (1 → N)

- Archivo de nómina demasiado grande para el banco o el ERP.  
- Un CSV nacional que debe partirse por compañía / sucursal / estado.  
- Partir por máximo de filas o tamaño de archivo.  
- Rangos de fechas (enero / febrero) en un solo extracto.

### Merge (N → 1)

- Unir `enero.xlsx` + `febrero.xlsx` + `marzo.xlsx` → `Q1.xlsx`.  
- Concatenar varios CSV del mismo layout.  
- Homologación ligera de columnas faltantes y deduplicación opcional.  
- Preparar un único lote para Gate o Match.

**Objetivo:** una definición persistente (“así partimos / unimos este tipo de archivo”) y una ejecución que entrega el/los archivo(s) listo(s) para el siguiente paso.

---

## 4. Alcance

### 4.1 Incluido (MVP)

| Incluido | Descripción |
|----------|-------------|
| Proyecto `project_kind=file_split_merge` | Alta, hub, miembros (PA/ED/CO/GE/CG) |
| Perfil de lectura | Tipo, encoding, captura, campos (reuso source / catálogo DMS) |
| Modo de operación | **Split** o **Merge** (por versión publicada; un proyecto puede publicar uno u otro, o ambos en fases) |
| Reglas Split | max_rows, max_bytes, split_by_column (+ valores), date_range (fase 2 si hace falta) |
| Reglas Merge | append (mismo layout), missing_columns (`error` \| `fill_empty`), dedupe opcional por clave |
| Publicar versión | Congela perfil + reglas de operación |
| Ejecución Split | 1 archivo → N salidas + manifiesto |
| Ejecución Merge | N archivos (≥2) → 1 salida + log |
| Preview | Muestra de partición / consolidación sin persistir (o con job `dry_run`) |
| Historial | Quién, cuándo, hashes, versión, métricas, conteo de partes |
| Formatos MVP | CSV, TXT delimitado/posicional, Excel (`.xlsx`); JSON/XML según soporte activo de parsers |

### 4.2 Excluido (MVP)

| Excluido | Motivo / fase |
|----------|----------------|
| Mapeo origen → destino de negocio | FilePipe |
| Conciliación por clave / informe only_A | File Match |
| Limpieza / normalización de valores | File Clean |
| Diff técnico sin clave | Retirado; usar Match |
| Fuzzy join / IA | Nunca en MVP |
| Carga automática a Worksheets | Fase 2 (`Merge → Worksheet`) |
| API HTTP pública | Tras FILE_OPS — diseño **API-ready** |
| Watch / Scheduler | Plataforma FILE_OPS |

### 4.3 Fronteras

```text
   FILE CLEAN (opcional)     →  normaliza
        ↓
 FILE SPLIT / MERGE          →  parte o une (este doc)
        ↓
   FILE GATE / FilePipe / Match
```

| Split/Merge | Pipe | Match | Clean |
|-------------|------|-------|-------|
| 1→N o N→1 sin cambiar semántica de negocio | Transforma a otro esquema | Compara e informa | Reescribe celdas con reglas |

---

## 5. Flujo de usuario (MVP)

```text
1. Crear proyecto File Split/Merge
2. Definir perfil de lectura (tipo, encoding, campos)
3. Elegir modo Split o Merge y definir reglas
4. Publicar versión
5. Ejecutar:
   - Split: subir 1 archivo → preview → confirmar → descargar ZIP / partes
   - Merge: subir N archivos → preview → confirmar → descargar consolidado
6. Consultar historial
7. (Opcional) Usar salida(s) en Gate / Pipe / Match (manual en MVP)
```

---

## 6. Módulos sugeridos

| # | Módulo | Spec | Contenido |
|---|--------|------|-----------|
| 1 | Ciclo de proyecto | [`definition_app_FILE_SPLIT_MERGE/project_lifecycle.md`](definition_app_FILE_SPLIT_MERGE/project_lifecycle.md) | Listado, alta, hub, miembros |
| 2 | Perfil de lectura | [`definition_app_FILE_SPLIT_MERGE/sm_profile.md`](definition_app_FILE_SPLIT_MERGE/sm_profile.md) | Cómo se lee el archivo (source-like) |
| 3 | Reglas Split / Merge | [`definition_app_FILE_SPLIT_MERGE/sm_rules.md`](definition_app_FILE_SPLIT_MERGE/sm_rules.md) | Partición y consolidación |
| 4 | Publicar | [`definition_app_FILE_SPLIT_MERGE/sm_publish.md`](definition_app_FILE_SPLIT_MERGE/sm_publish.md) | Borrador → versión publicada |
| 5 | Ejecución | [`definition_app_FILE_SPLIT_MERGE/sm_run.md`](definition_app_FILE_SPLIT_MERGE/sm_run.md) | Upload, preview, job, artifacts |
| 6 | Historial | [`definition_app_FILE_SPLIT_MERGE/sm_history.md`](definition_app_FILE_SPLIT_MERGE/sm_history.md) | Listado y detalle de jobs |
| — | Integración | [`definition_app_FILE_SPLIT_MERGE/sm_integration.md`](definition_app_FILE_SPLIT_MERGE/sm_integration.md) | Kind, URLs, roles, reuso DMS, **API-ready** |

Método: **definir → prototipar → revisar → implementar solo con «Desarrolla el módulo»**.

---

## 7. Reglas de negocio (borrador)

| ID | Regla |
|----|--------|
| SM1 | Solo se ejecuta contra versión **publicada**. |
| SM2 | La versión declara `operation` ∈ {`split`, `merge`} (MVP: una operación por versión publicada). |
| SM3 | Split: exactamente **1** archivo de entrada; ≥1 parte de salida (si 0 filas → `failed` o vacío documentado). |
| SM4 | Merge: **≥2** archivos de entrada; 1 archivo de salida. |
| SM5 | Fallo de parseo → job `failed` (no entregar salida parcial engañosa). |
| SM6 | Todas las partes Split comparten el mismo layout/perfil (salvo manifiesto). |
| SM7 | Merge exige layout compatible (mismas columnas / mismos campos del perfil); columnas faltantes según política publicada. |
| SM8 | Aislamiento por `Company` + membresía. |
| SM9 | El Job debe ser invocable igual desde UI y, en el futuro, desde [`PLATFORM_API`](PLATFORM_API.md). |

---

## 8. Catálogo de reglas MVP (orientativo)

### 8.1 Split

| Código | Descripción | Params (borrador) |
|--------|-------------|-------------------|
| `max_rows` | Partir cada N filas de datos | `n` (int ≥ 1) |
| `max_bytes` | Partir al superar tamaño aproximado | `bytes` |
| `split_by_column` | Una salida por valor distinto de un campo | `field_name`, `include_empty?` |
| `keep_header` | Repetir encabezado en cada parte (delimited/xlsx) | `bool` (default true) |

**Fase 2:** `date_range` (campo fecha + granularidad mes/día), `round_robin`, límites de número máximo de partes.

### 8.2 Merge

| Código | Descripción | Params (borrador) |
|--------|-------------|-------------------|
| `append` | Concatenar filas en orden de upload | (default) |
| `missing_columns` | Política si falta una columna del perfil | `error` \| `fill_empty` |
| `dedupe_rows` | Eliminar duplicados tras unir | `keys[]`, `keep` first/last |
| `include_header` | Una sola fila de encabezado en salida | `bool` |

**Fase 2:** unión por clave (outer/inner), ordenación global, Merge → Worksheet.

Detalle: [`definition_app_FILE_SPLIT_MERGE/sm_rules.md`](definition_app_FILE_SPLIT_MERGE/sm_rules.md).

---

## 9. Modelo conceptual (borrador)

```text
Company
  └── Project (kind=file_split_merge)
        ├── SplitMergeConfig (visibilidad, flags)
        ├── SplitMergeVersion (draft | published)
        │     ├── read_profile (tipo, encoding, campos…)
        │     ├── operation: split | merge
        │     └── rules[] (orden, code, params)
        └── SplitMergeJob
              ├── operation
              ├── input_files[] + hashes
              ├── output_files[] + hashes  (1..N)
              ├── manifest / metrics
              └── status (queued | running | completed | failed)
```

---

## 10. Roles

| Acción | PA | ED | CO | GE |
|--------|----|----|----|-----|
| Crear proyecto / miembros | ✓ | — | — | — |
| Editar perfil y reglas (borrador) | ✓ | ✓ | — | — |
| Publicar versión | ✓ | ✓* | — | — |
| Ejecutar / descargar salidas | ✓ | ✓ | — | ✓ |
| Ver historial / metadatos | ✓ | ✓ | ✓ | ✓ |

\*Publicar: alineado a política de Clean/Gate (confirmar en `sm_integration`).

---

## 11. API-ready (sin implementar API ahora)

| Requisito de diseño | Detalle |
|---------------------|---------|
| `kind` | `file_split` y `file_merge`, **o** `file_split_merge` + campo `operation` |
| Entrada Split | 1 archivo + `project_slug` + versión publicada |
| Entrada Merge | N archivos (`files[]`) + proyecto + versión |
| Salida Split | URLs de partes + manifiesto + `job_id` |
| Salida Merge | `output_url` + `job_id` |
| Runner | Servicio desacoplado de la vista HTML |

```http
POST /api/v1/jobs/run
kind=file_split
project_slug=particion-nomina
version=published
file=<bytes>
```

```http
POST /api/v1/jobs/run
kind=file_merge
project_slug=consolidado-q1
version=published
files[]=<bytes>…
```

---

## 12. Casos de negocio

| ID | Caso |
|----|------|
| C1 | Nómina nacional → Split por `sucursal` → N CSV al banco |
| C2 | Extracto de 500k filas → Split por `max_rows=50000` → Gate por partes |
| C3 | Tres meses de ventas → Merge append → un Excel para Pipe |
| C4 | Varios CSV del mismo layout con columnas opcionales → Merge `fill_empty` + dedupe |

---

## 13. Criterio APP_FACTORY

1. Reutiliza Company + seguridad + billing.  
2. `project_kind=file_split_merge` claro; no solapa Pipe ni Match.  
3. MVP &lt; 1 fase (formatos + reglas acotadas).  
4. Specs en `definition_app_FILE_SPLIT_MERGE/` + prototipos antes de código.  
5. Parsers/serializers **compartidos** (sin fork).  
6. Job listo para PLATFORM_API al cierre de FILE_OPS.

---

## 14. Prioridad y siguientes pasos

| Orden | Paso |
|-------|------|
| 1 | Cerrar specs M1–M3 (`project_lifecycle`, `sm_profile`, `sm_rules`) |
| 2 | Prototipos `prototype/file_split_merge/` |
| 3 | Implementar por módulo con OK explícito |
| 4 | Publicar + run + history |
| 5 | (Oleada) Data Profiler → Repair → Watch… |
| 6 | **Al finalizar FILE_OPS apps** → [`PLATFORM_API`](PLATFORM_API.md) |

---

## 15. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Índice ops; Split/Merge en §2 |
| [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) | Specs por módulo |
| [`FILE_CLEAN.md`](FILE_CLEAN.md) | Hermano FILE_OPS (hecho) |
| [`FILE_MATCH.md`](FILE_MATCH.md) | No confundir con Merge |
| [`DataMappingStudio.md`](DataMappingStudio.md) | Parsers / serializers |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Ejecución remota (fase posterior) |
| [`APP_FACTORY.md`](APP_FACTORY.md) | Prioridad de fábrica |
| [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | Mensajes / `error_code` |

---

*Documento vivo. Actualizar estado al implementar módulos.*
