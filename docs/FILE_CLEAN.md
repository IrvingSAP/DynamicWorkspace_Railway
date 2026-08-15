# FILE CLEAN — Limpieza y normalización de archivos

> **Nombre mnemotécnico:** `FILE_CLEAN`  
> Alias: *Limpiador de archivos* · *Normalizador pre-calidad*  
> Archivo: [`docs/FILE_CLEAN.md`](FILE_CLEAN.md)  
> Estado: **definición de producto** (sin implementación)  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §4 · prioridad ⭐⭐⭐⭐⭐  
> Specs por módulo: [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/)  
> Estilo: hermano de [`FILE_GATE.md`](FILE_GATE.md) / [`DataMappingStudio.md`](DataMappingStudio.md)

### Rama de desarrollo y despliegues (cuando se abra)

| Ítem | Valor |
|------|--------|
| **Rama Git sugerida** | `feature/file-clean` |
| **Base** | `main` |
| **Despliegues Railway** | Solo desde `main` tras merge del MVP |
| **API pública** | **Después** de las apps FILE_OPS; Clean debe nacer **API-ready** (Job + `kind`) — ver [`PLATFORM_API.md`](PLATFORM_API.md) |

---

## 1. Resumen ejecutivo

**File Clean** es un aplicativo de DynamicWorkspace que permite definir un **perfil de limpieza versionado**, aplicar reglas explícitas a un archivo y entregar un **archivo normalizado** + log auditable — típico **antes** de validar (File Gate) o transformar (FilePipe / Match).

```text
Definir cómo se lee el archivo
        →
Definir reglas de limpieza (ordenadas)
        →
Publicar versión
        →
Subir archivo → preview / ejecutar
        →
Descargar archivo limpio + log de cambios
```

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Muchos rechazos de Gate o fallos de Pipe no son de “estructura incorrecta”, sino datos **sucios** (espacios, encoding, fechas, decimales, duplicados) |
| **Solución** | Proyecto reutilizable: perfil de lectura + reglas de limpieza publicadas + job con salida limpia y traza |
| **Beneficio** | Menos scripts ad-hoc; calidad repetible; mismo lenguaje de roles/versiones que el resto de la suite |
| **Audiencia** | Operaciones, calidad de datos, integradores, proveedores internos |

### Posicionamiento

| Alternativa | Limitación | Diferenciador File Clean |
|-------------|------------|--------------------------|
| Reglas dentro de FilePipe | Pipe es ETL de negocio; mezcla limpieza con mapeo destino | Clean = **solo normalizar**; salida = mismo “tipo” de archivo, listo para Gate/Pipe |
| Corregir a mano en Excel | No audita, no escala | Job + log campo a campo |
| File Gate | Solo valida; no reescribe | Clean **reescribe** con reglas explícitas |
| File Repair (propuesto) | Dirigido por errores de un job Gate | Clean = reglas **a priori**; Repair = correcciones desde rechazos |

### Relación con la plataforma

| Pieza | Relación |
|-------|----------|
| Chasis (Company, seguridad, billing, roles) | Reutilizado al 100 % |
| DMS — parsers, intake, catálogo de reglas | **Núcleo** (motor compartido; no fork) |
| File Gate | Consumidor típico post-Clean |
| FilePipe / Match | Consumidores opcionales post-Clean |
| [`PLATFORM_API.md`](PLATFORM_API.md) | `kind=file_clean` cuando se implemente la API (fase posterior a FILE_OPS) |

---

## 2. Importancia

1. Completa el hueco **antes** de Gate en el pipeline FILE_OPS.  
2. Alto reuso del motor de reglas DMS.  
3. Diferenciador claro sin ser un segundo FilePipe.  
4. Prepara Jobs homogéneos para Watch / Scheduler / **PLATFORM API** al final de la oleada FILE_OPS.

---

## 3. Problema que resuelve

- TXT/CSV con espacios, BOM o Latin-1 vs UTF-8.  
- Fechas y números con formatos regionales mixtos.  
- Códigos/documentos/teléfonos sin estandarizar.  
- Valores vacíos representados como `"null"`, `"N/A"`, etc.  
- Duplicados de fila antes de conciliar o validar.

**Objetivo:** una definición persistente (“así limpiamos este tipo de archivo”) y una ejecución que entrega el archivo listo para el siguiente paso.

---

## 4. Alcance

### 4.1 Incluido (MVP)

| Incluido | Descripción |
|----------|-------------|
| Proyecto `project_kind=file_clean` | Alta, hub, miembros (PA/ED/CO/GE/CG) |
| Perfil de lectura | Tipo de archivo, encoding, captura, campos (reuso source / catálogo DMS) |
| Reglas de limpieza | Catálogo versionable, ordenadas, por campo o globales |
| Publicar versión | Congela perfil + reglas; solo se ejecuta lo publicado |
| Ejecución | Upload → preview (muestra) → run → descarga limpia + log |
| Historial | Quién, cuándo, hash entrada/salida, versión, métricas |
| Formatos MVP | Alinear a parsers DMS: CSV, TXT delimitado/posicional, Excel (`.xlsx`), JSON/XML según soporte activo |

### 4.2 Excluido (MVP)

| Excluido | Motivo / fase |
|----------|----------------|
| Mapeo origen → destino de negocio | FilePipe |
| Validación de contrato / rechazos | File Gate |
| Corrección dirigida por errores Gate | File Repair (FILE_OPS) |
| IA que “adivina” limpiezas | Nunca en MVP; solo reglas explícitas |
| API HTTP pública | Tras finalizar apps FILE_OPS — diseño **API-ready** desde ya |
| Watch / Scheduler | FILE_OPS plataforma; Clean expone Job reusable |
| Carga a Worksheets | Fuera de alcance |

### 4.3 Fronteras

```text
Structure Scout / Profiler  →  entiende estructura / calidad
        ↓
   FILE CLEAN               →  normaliza (este doc)
        ↓
   FILE GATE                →  valida contrato
        ↓
   FilePipe / Reverse / Match
```

| Clean | Pipe | Gate | Repair |
|-------|------|------|--------|
| Reescribe con reglas de limpieza | Transforma a otro esquema/formato de negocio | No reescribe; informa OK/error | Reescribe a partir de errores de un job Gate |

---

## 5. Flujo de usuario (MVP)

```text
1. Crear proyecto File Clean
2. Definir perfil de lectura (tipo, encoding, campos)
3. Definir reglas de limpieza (orden)
4. Publicar versión
5. Ejecutar: subir archivo → preview → confirmar
6. Descargar archivo limpio + log
7. (Opcional) Enviar salida a Gate / Pipe / Match (manual en MVP; cadena automática = Watch/API después)
```

---

## 6. Módulos sugeridos

| # | Módulo | Spec | Contenido |
|---|--------|------|-----------|
| 1 | Ciclo de proyecto | [`definition_app_FILE_CLEAN/project_lifecycle.md`](definition_app_FILE_CLEAN/project_lifecycle.md) | Listado, alta, hub, miembros |
| 2 | Perfil de lectura | [`definition_app_FILE_CLEAN/clean_profile.md`](definition_app_FILE_CLEAN/clean_profile.md) | Cómo se lee el archivo (source-like) |
| 3 | Reglas de limpieza | [`definition_app_FILE_CLEAN/clean_rules.md`](definition_app_FILE_CLEAN/clean_rules.md) | Catálogo, orden, parámetros |
| 4 | Publicar | [`definition_app_FILE_CLEAN/clean_publish.md`](definition_app_FILE_CLEAN/clean_publish.md) | Borrador → versión publicada |
| 5 | Ejecución | [`definition_app_FILE_CLEAN/clean_run.md`](definition_app_FILE_CLEAN/clean_run.md) | Upload, preview, job, artifacts |
| 6 | Historial | [`definition_app_FILE_CLEAN/clean_history.md`](definition_app_FILE_CLEAN/clean_history.md) | Listado y detalle de jobs |
| — | Integración | [`definition_app_FILE_CLEAN/fc_integration.md`](definition_app_FILE_CLEAN/fc_integration.md) | Kind, URLs, roles, reuso DMS, **API-ready** |

Método: **definir → prototipar → revisar → implementar solo con «Desarrolla el módulo»**.

---

## 7. Reglas de negocio (borrador)

| ID | Regla |
|----|--------|
| FC1 | Solo se ejecuta contra versión **publicada**. |
| FC2 | Toda regla aplicada queda en el log (campo, valor antes/después, regla, fila). |
| FC3 | No hay limpiezas implícitas “mágicas”; solo reglas del catálogo del proyecto. |
| FC4 | El archivo de salida usa el mismo `file_type` de lectura salvo regla explícita de encoding/BOM. |
| FC5 | Fallo de parseo → job `failed` (no entregar salida parcial engañosa). |
| FC6 | Aislamiento por `Company` + membresía. |
| FC7 | El Job debe ser invocable igual desde UI y, en el futuro, desde [`PLATFORM_API`](PLATFORM_API.md) (`kind=file_clean`). |

---

## 8. Catálogo de reglas MVP (orientativo)

| Código | Descripción | Ámbito |
|--------|-------------|--------|
| `trim` | Quitar espacios extremos | Campo |
| `strip_invisible` | Caracteres no imprimibles / zero-width | Campo |
| `case_upper` / `case_lower` | Mayúsculas / minúsculas | Campo |
| `date_normalize` | Parsear fechas a formato canónico del proyecto | Campo |
| `number_normalize` | Separadores decimales/miles | Campo |
| `null_tokens` | Mapear `""`, `N/A`, `null` → vacío | Campo / global |
| `replace_map` | Mapa valor completo → valor (match **exacto**; reuso DMS) | Campo |
| `replace` | Find/replace **dentro** del string (reuso DMS) | Campo |
| `compose` | Plantilla: literal + `{value}` / `{field:…}` / `{seq}` | Campo |
| `dedupe_rows` | Eliminar filas duplicadas (clave configurable) | Global |
| `encoding_normalize` | Forzar UTF-8 / quitar BOM | Archivo |

Detalle de semántica y params: [`definition_app_FILE_CLEAN/clean_rules.md`](definition_app_FILE_CLEAN/clean_rules.md).

**Fase 2:** teléfonos, documentos nacionales, padding posicional fino, `substring` como op de campo, `regex` en `replace`, tokens de porción `{field:name:start,len}` en `compose`.

---

## 9. Modelo conceptual (borrador)

```text
Company
  └── Project (kind=file_clean)
        ├── CleanConfig (visibilidad, flags)
        ├── CleanProfileVersion (draft | published)
        │     ├── read_profile (tipo, encoding, campos…)
        │     └── rules[] (orden, code, params, field_ref?)
        └── CleanJob
              ├── input_file + hash
              ├── output_file + hash
              ├── change_log / metrics
              └── status (queued | running | completed | failed)
```

---

## 10. Roles

| Acción | PA | ED | CO | GE |
|--------|----|----|----|-----|
| Crear proyecto / miembros | ✓ | — | — | — |
| Editar perfil y reglas (borrador) | ✓ | ✓ | — | — |
| Publicar versión | ✓ | ✓* | — | — |
| Ejecutar limpieza / descargar salida | ✓ | ✓ | — | ✓ |
| Ver historial / metadatos | ✓ | ✓ | ✓ | ✓ |

\*Publicar: alineado a política de Pipe/Gate (confirmar en `fc_integration`).

---

## 11. API-ready (sin implementar API ahora)

**Decisión de roadmap:** la [`PLATFORM_API`](PLATFORM_API.md) se trabajará **al finalizar** el desarrollo de las nuevas propuestas FILE_OPS. File Clean debe diseñarse para encajar sin refactor mayor.

| Requisito de diseño | Detalle |
|---------------------|---------|
| `kind` | `file_clean` |
| Entrada API futura | 1 archivo + `project_slug` + `version=published` |
| Salida API futura | `output_url` (archivo limpio) + `report_url` (log) + `job_id` |
| Runner | Servicio de ejecución desacoplado de la vista HTML |
| Códigos | Reusar / extender catálogo de errores alineado a UI_MESSAGES |

Ejemplo conceptual (futuro, no MVP de esta app):

```http
POST /api/v1/jobs/run
kind=file_clean
project_slug=limpieza-nomina
version=published
file=<bytes>
```

---

## 12. Casos de negocio

| ID | Caso |
|----|------|
| C1 | Proveedor envía CSV con BOM y fechas `dd/mm/yyyy` → Clean → Gate |
| C2 | Nómina TXT con espacios y códigos en minúsculas → Clean → Pipe |
| C3 | Dos extractos antes de Match: normalizar claves y quitar duplicados |
| C4 | Estandarizar encoding Latin-1 → UTF-8 antes de validar |

---

## 13. Criterio APP_FACTORY

1. Reutiliza Company + seguridad + billing.  
2. `project_kind=file_clean` claro; no solapa Pipe sin diferenciador.  
3. MVP &lt; 1 fase (formatos + reglas acotadas).  
4. Specs en `definition_app_FILE_CLEAN/` + prototipos antes de código.  
5. Motor de reglas **compartido** con DMS (sin fork).  
6. Job listo para PLATFORM_API al cierre de FILE_OPS.

---

## 14. Prioridad y siguientes pasos

| Orden | Paso |
|-------|------|
| 1 | Cerrar specs M1–M3 (`project_lifecycle`, `clean_profile`, `clean_rules`) |
| 2 | Prototipos `prototype/file_clean/` |
| 3 | Implementar por módulo con OK explícito |
| 4 | Publicar + run + history |
| 5 | (Oleada) Diff / Split-Merge / Profiler… |
| 6 | **Al finalizar FILE_OPS apps** → implementar [`PLATFORM_API`](PLATFORM_API.md) incluyendo `file_clean` |

---

## 15. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Paraguas ops; Clean §4 |
| [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/) | Specs por módulo |
| [`FILE_GATE.md`](FILE_GATE.md) | Siguiente paso típico del pipeline |
| [`DataMappingStudio.md`](DataMappingStudio.md) | Motor de reglas / parsers |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Ejecución remota (fase posterior) |
| [`APP_FACTORY.md`](APP_FACTORY.md) | Prioridad de fábrica |
| [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | Mensajes / `error_code` |

---

*Documento vivo. Actualizar estado al abrir rama e implementar módulos.*
