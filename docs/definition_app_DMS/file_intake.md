# File intake

Proceso y especificación del **módulo de carga de archivos** en Data Mapping Studio: selección física del archivo (browse), subida al servidor, validación inicial y preview. Aplica en **dos contextos** distintos: asistente de definición (archivo muestra) y ejecución (archivo de producción).

> Estado: **MVP implementado** (muestra + producción upload, preview, detección heurística, storage bajo `MEDIA_ROOT/dms/`).  
> Complementa: `source_definition.md`. Ejecución completa: [`transform_execution.md`](transform_execution.md).  
> Integración: [`dms_integration.md`](dms_integration.md).  
> Mensajes UI: [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.8.

---

## Propósito

Permitir que el usuario **seleccione un archivo del disco local** (ventana browse del sistema operativo), lo suba de forma segura al servidor y obtenga **señales de validación** (extensión, tamaño, encoding sugerido) antes de continuar con la definición o la transformación.

El usuario **no escribe rutas de servidor** ni elige carpetas en el filesystem del backend: solo selecciona un archivo local; el sistema asigna la ruta de almacenamiento interna.

---

## Dos contextos de uso

| Contexto | Cuándo | Permiso | Archivo | Persistencia |
|----------|--------|---------|---------|--------------|
| **Muestra (wizard)** | Definición origen — Pasos 1–4 | `ED` o `PA` | Archivo de ejemplo | `DmsSampleFile` |
| **Producción (ejecución)** | Fase C — tab Ejecutar | `GE`, `ED` o `PA` | Archivo real | `DmsExecutionJob` |

```mermaid
flowchart TB
    subgraph wizard [Definicion origen]
        W1[Browse archivo muestra]
        W2[Upload + validar]
        W3[Preview parseado]
        W4[Sugerir SourceProfile]
        W1 --> W2 --> W3 --> W4
    end
    subgraph exec [Ejecucion Fase C]
        E1[Browse archivo produccion]
        E2[Upload + validar]
        E3[Preview opcional dry run]
        E4[Job completo]
        E1 --> E2 --> E3 --> E4
    end
```

> Detalle del job completo, nombre de salida y descarga: `transform_execution.md`.

---

## Alcance

| Incluido | Excluido |
|----------|----------|
| UI de selección (browse, drag & drop opcional) | Definición de campos (`source_definition.md`) |
| Validación extensión vs `SourceFileType` | Mapeo y reglas de transformación |
| Límites de tamaño y tipos MIME | Serialización destino (`target_definition.md`) |
| Almacenamiento temporal del archivo subido | Permisos de proyecto (`project_lifecycle.md`) |
| Detección sugerida encoding / line ending | Historial completo del job (→ `transform_execution.md`) |
| Preview de primeras filas parseadas | Scheduling / API (Fase 3) |

---

## Interfaz — selección física del archivo

### Patrón UI (MVP)

| Elemento | Comportamiento |
|----------|----------------|
| **Botón «Seleccionar archivo»** | Abre el diálogo nativo del SO (`<input type="file">` oculto + `click()`). Filtro de extensiones según `SourceFileType.extensions` del proyecto |
| **Zona drag & drop** (opcional) | Misma validación que browse; resalta al arrastrar |
| **Nombre mostrado** | Tras seleccionar: `nombre_original.ext` + tamaño legible (ej. `2.4 MB`) |
| **Botón «Quitar»** | Limpia selección antes de subir |
| **Barra de progreso** | Durante upload HTTP (multipart) |
| **Estado** | `pendiente` → `subiendo` → `validado` \| `rechazado` |

**Flujo del usuario:**

1. Clic en **Seleccionar archivo** (o arrastrar a la zona).
2. El SO muestra la ventana browse; el usuario elige un archivo local.
3. El cliente valida extensión y tamaño máximo en frontend (feedback inmediato).
4. Clic en **Subir** / **Continuar** → POST multipart al servidor.
5. El servidor valida, almacena y devuelve metadatos + sugerencias (encoding, delimitador…).
6. Preview de filas (wizard) o paso a dry run / ejecutar (producción).

### Atributos del input file

| Atributo | Valor |
|----------|-------|
| `accept` | Extensiones del `SourceFileType` activo. Ej: `.txt,.csv` |
| `multiple` | `false` — un archivo por operación en MVP |
| `capture` | No usar (solo escritorio/servidor de archivos) |

---

## Validaciones al subir

| Regla | Momento | Comportamiento |
|-------|---------|----------------|
| Extensión permitida | Cliente + servidor | Error: «Tipo de archivo no permitido para este proyecto» |
| Tamaño ≤ límite contexto | Cliente + servidor | Error con límite indicado |
| Proyecto con `SourceProfile` (ejecución) | Servidor | Error si no hay versión publicada |
| Versión publicada (ejecución) | Servidor | Error si solo hay borrador |
| Permiso `update` (muestra) / `execute` (producción) | Servidor | 403 |
| Archivo vacío (0 bytes) | Servidor | Error |
| Nombre seguro | Servidor | Sanitizar; rechazar path traversal (`../`) |

### Límites de tamaño (MVP)

| Contexto | Límite sugerido | Motivo |
|----------|-----------------|--------|
| Archivo muestra (wizard) | **10 MB** | Preview síncrono en navegador |
| Archivo producción — preview / dry run | **50 MB** | Primeras N filas en memoria |
| Archivo producción — job completo | **500 MB** | Cola asíncrona + streaming (Fase 2 si >50 MB sync) |

> Ajustables por plan o configuración de plataforma.

---

## Detección automática (post-upload)

Tras almacenar la muestra, File intake ejecuta heurísticas y **sugiere** valores para el asistente (`source_definition.md`); el usuario confirma o corrige.

| Señal | Heurística | Catálogo |
|-------|------------|----------|
| Tipo por extensión | `.csv` → `csv`; `.xlsx` → `xlsx` | `SourceFileType` |
| TXT posicional vs delimitado | Longitud de línea constante vs separadores | — |
| Encoding | `chardet` + fallback `utf-8` | `CharsetEncoding` (`auto` → sugerencia) |
| Final de línea | Muestra de bytes `\n` / `\r\n` | `LineEnding` |
| Delimitador CSV/TXT | Frecuencia de `,` `;` `\t` | — |

Respuesta API de ejemplo:

```json
{
  "stored_file_id": "a1b2c3d4-…",
  "original_filename": "nomina_julio.txt",
  "size_bytes": 2457600,
  "suggestions": {
    "file_type_code": "txt_fixed",
    "encoding_code": "latin-1",
    "line_ending_code": "lf",
    "delimiter": null
  },
  "preview_rows": [
    {"line": 1, "raw": "12345JUAN      2500001", "parsed": null}
  ]
}
```

---

## Almacenamiento en servidor

El usuario **no elige carpeta** en el servidor. El backend genera rutas internas deterministas.

### Convención de rutas (filesystem u object storage)

```
{MEDIA_ROOT}/dms/
  {company_id}/
    projects/{project_id}/
      samples/{sample_file_id}/
        original/{sanitized_filename}
      jobs/{job_id}/
        input/{stored_filename}
```

| Segmento | Descripción |
|----------|-------------|
| `company_id` | UUID de `Company` — aislamiento tenant |
| `project_id` | UUID de `Project` (`project_kind=dms`) |
| `sample_file_id` | UUID del registro `SampleFile` |
| `job_id` | UUID del `ExecutionJob` (solo producción) |
| `sanitized_filename` | Nombre original limpio; colisión → sufijo `_1`, `_2` |

**Nombre almacenado interno (input):** `{uuid}_{sanitized_basename}` para evitar colisiones y ocultar nombres conflictivos.

> La **salida** del job (archivo destino transformado) se guarda bajo `jobs/{job_id}/output/` — ver `transform_execution.md`.

### Retención (TTL)

| Tipo | Retención MVP | Acceso |
|------|---------------|--------|
| `SampleFile` | Mientras exista el borrador o 90 días sin uso | Solo usuarios con `update` |
| Input de job | **7 días** tras completar el job | Metadatos en historial; re-descarga según política |
| Output de job | **7 días** — enlace de descarga | Usuario con `execute` o `view` |

Purgado automático por tarea programada; el historial (`ExecutionJob`) conserva metadatos aunque el binario expire.

---

## Modelo conceptual

### `SampleFile`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `project_id` | FK | Proyecto |
| `project_version_id` | FK | Borrador en edición (nullable si suelta) |
| `original_filename` | string | Nombre del archivo del usuario |
| `stored_path` | string | Ruta relativa bajo `dms_storage_root` |
| `size_bytes` | integer | — |
| `content_hash` | string | SHA-256 del contenido |
| `mime_type` | string | Detectado o declarado |
| `uploaded_by_id` | FK | Usuario |
| `suggestions` | JSON | Resultado de auto-detección |
| `created_at` | datetime | — |

### `StoredInputFile` (referencia en job)

No es entidad separada en MVP: los campos de input viven en `ExecutionJob` (ver `transform_execution.md`).

---

## API / endpoints sugeridos (MVP)

| Método | Ruta | Contexto | Descripción |
|--------|------|----------|-------------|
| POST | `/api/dms/projects/{id}/samples/` | Wizard | Subir archivo muestra |
| GET | `/api/dms/projects/{id}/samples/{sample_id}/preview/` | Wizard | Primeras N filas parseadas |
| DELETE | `/api/dms/projects/{id}/samples/{sample_id}/` | Wizard | Eliminar muestra |
| POST | `/api/dms/projects/{id}/execute/upload/` | Ejecución | Subir archivo producción; crea `ExecutionJob` en estado `uploaded` |

Upload: `multipart/form-data`, campo `file`.

---

## Integración con catálogos

| Catálogo | Uso en File intake |
|----------|-------------------|
| `SourceFileType` | Filtro `accept`; validación extensión |
| `CharsetEncoding` | Sugerencia `encoding_code` |
| `LineEnding` | Sugerencia `line_ending_code` |

---

## Seguridad

| Tema | Decisión |
|------|----------|
| Path traversal | Rechazar nombres con `..`, `/`, `\` en rutas finales |
| Escaneo antivirus | Fase 2 (opcional en entornos enterprise) |
| Aislamiento | Archivos bajo `project_id`; sin lectura cruzada entre proyectos |
| Autenticación | Todas las rutas requieren sesión; permisos según contexto |

---

## Casos de uso

### FI-01 — Muestra en wizard origen

| | |
|---|---|
| **Actor** | Diseñador |
| **Flujo** | Browse → sube `nomina.txt` → sistema sugiere `txt_fixed` + `latin-1` → preview 10 líneas |
| **Resultado** | `SampleFile` guardado; usuario continúa Paso 4 con campos sugeridos |

### FI-02 — Archivo producción mensual

| | |
|---|---|
| **Actor** | Operador (`execute`) |
| **Flujo** | Tab Ejecutar → browse → sube `nomina_202507.txt` → validación OK |
| **Resultado** | Input en `jobs/{job_id}/input/`; listo para dry run o ejecutar |

### FI-03 — Extensión no permitida

| | |
|---|---|
| **Flujo** | Proyecto definido como CSV; usuario selecciona `.xlsx` |
| **Resultado** | Error en cliente antes de upload; mensaje claro |

### FI-04 — Archivo demasiado grande

| | |
|---|---|
| **Flujo** | Muestra de 25 MB en wizard (límite 10 MB) |
| **Resultado** | Rechazo con sugerencia: usar subconjunto o archivo más pequeño |

---

## Implementación en código (MVP)

| Pieza | Ubicación | Estado |
|-------|-----------|--------|
| `DmsSampleFile` / `DmsExecutionJob` | `apps/dms/file_intake/models.py` | MVP hecho |
| Storage rutas tenant | `storage_service.py` | MVP hecho |
| Detección heurística | `detection_service.py` | MVP hecho |
| Upload muestra / producción | `file_intake_persistence_service.py` | MVP hecho |
| Hub UI | `/app/filepipe/proyectos/<slug>/archivo/` | MVP hecho |
| Transformación / descarga | [`transform_execution.md`](transform_execution.md) | MVP hecho |

## Pendiente de definir

- [x] MVP browse + upload muestra + preview
- [x] MVP upload producción → job `uploaded`
- [x] Motor dry run / ejecución completa (`transform_execution.md`)
- [ ] Chunked upload para archivos >100 MB (Fase 2)
- [ ] Reutilizar última muestra entre versiones del proyecto
- [ ] Integración S3 / Azure Blob vs filesystem local

---

## Fase

| Alcance | Fase |
|---------|------|
| Browse + upload muestra + preview wizard | MVP | Hecho |
| Browse + upload producción + validación | MVP | Hecho |
| Auto-detección encoding / tipo / delimitador | MVP | Hecho |
| Drag & drop | MVP | Hecho |
| Upload asíncrono chunked | Fase 2 | Pendiente |

---

## Documentos relacionados (DMS)

| Documento | Relación |
|-----------|----------|
| [`source_definition.md`](source_definition.md) | Consume sugerencias; no define upload (**MVP origen ya en código**) |
| [`transform_execution.md`](transform_execution.md) | Job, salida, descarga tras upload producción |
| [`system_catalogs.md`](system_catalogs.md) | `SourceFileType`, `TextReadFormat` |
| [`project_lifecycle.md`](project_lifecycle.md) | Fase C; permisos vía `ProjectMembership` |
| [`dms_integration.md`](dms_integration.md) | Tenant `Company`, rutas storage |
| [`target_definition.md`](target_definition.md) | No aplica a intake (solo salida en ejecución) |
