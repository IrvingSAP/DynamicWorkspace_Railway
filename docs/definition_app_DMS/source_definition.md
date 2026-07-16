# Source definition

Proceso y especificación del **Módulo 1** de Data Mapping Studio: definir cómo debe interpretarse un archivo de origen y persistir esa configuración como `SourceProfile`.

> Estado: **MVP implementado** (asistente 6 pasos, borrador/publicación, `txt_fixed` / delimitado / `xlsx` / `json` / `xml`, modos de captura incl. patrón y blancos).  
> Módulos relacionados: [`file_intake.md`](file_intake.md), [`transform_execution.md`](transform_execution.md), [`field_mapping.md`](field_mapping.md).  
> Prerrequisitos: perfiles y mapeos en `DmsMappingVersion`.  
> Plataforma: [`dms_integration.md`](dms_integration.md).  
> Mensajes UI: [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.8.  
> Mensajes de informe: catálogo `ExecutionErrorCode` ([`system_catalogs.md`](system_catalogs.md) §7).

---

## Propósito

Permitir que el usuario configure **paso a paso** las características que debe cumplir o esperar un archivo fuente, sin depender de programación.

El resultado es un `SourceProfile` reutilizable: el motor lo aplica cada vez que se procese un archivo que cumpla esa definición.

Sin un perfil de origen válido, no hay parseo de filas ni campos disponibles para mapeo ni transformación.

---

## Alcance de este documento

| Incluido | Excluido (otro módulo / app) |
|----------|------------------------------|
| Tipo de archivo soportado | Selección del archivo de producción a procesar |
| Rango de líneas a capturar (inicio / fin) | Ejecución masiva del job |
| Definición de campos y validaciones por campo | Mapeo origen → destino |
| Reglas globales de contenido | Reglas de transformación |
| Configuración del informe de procesamiento | Historial de ejecuciones |
| Modelo `SourceProfile` y JSON de configuración | Generación del archivo destino |

> **Nota:** el flujo de *subir archivo muestra*, *preview en wizard* y *selección de archivo a procesar* está en [`file_intake.md`](file_intake.md) y la ejecución en [`transform_execution.md`](transform_execution.md).

---

## Responsabilidades

| Sí | No |
|----|-----|
| Asistente paso a paso de definición del origen | Procesar archivos de producción |
| Tipo de archivo, rango de captura, campos | Mapeo a destino |
| Validación de tipo de dato por campo | Transformaciones |
| Reglas globales de caracteres permitidos/excluidos | Informe final de ejecución (solo se define qué debe contener) |
| Persistencia de `SourceProfile` | Validación contra esquema destino |

---

## Proceso de definición (asistente paso a paso)

El usuario recorre **6 pasos** en orden. Cada paso persiste borrador; puede volver atrás sin perder datos.

```mermaid
flowchart LR
    S1[Paso 1 Tipo de archivo]
    S2[Paso 2 Linea inicio]
    S3[Paso 3 Linea fin]
    S4[Paso 4 Campos]
    S5[Paso 5 Reglas globales]
    S6[Paso 6 Informe]
    Save[Guardar SourceProfile]
    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> Save
```

---

### Paso 1 — Tipo de archivo a recibir

El sistema muestra los tipos habilitados desde el catálogo **`SourceFileType`** (mantenimiento con listado y CRUD — ver `system_catalogs.md`). El usuario elige uno; el resto del asistente adapta sus opciones según el `code` y el `config_schema` del tipo seleccionado.

> Los tipos **no están fijos en código**. Un administrador puede activar, desactivar u ordenar formatos sin redeploy.

| Campo en perfil | Origen |
|-----------------|--------|
| `file_type_code` | `SourceFileType.code` seleccionado |
| Parámetros del asistente | `SourceFileType.config_schema` + campos comunes |

**Tipos previstos en datos semilla (referencia inicial, administrables):**

| Código | Nombre | Fase |
|--------|--------|------|
| `txt_fixed` | TXT posicional | MVP |
| `txt_delimited` | TXT delimitado | MVP |
| `csv` | CSV | MVP |
| `xlsx` | Excel | MVP |
| `json` | JSON | MVP |
| `xml` | XML | MVP |

Parámetros comunes a todos los tipos (se configuran en este paso o al guardar). Valores desde catálogo **`TextReadFormat`** (`system_catalogs.md` — mantenimiento de `CharsetEncoding` y `LineEnding`):

| Parámetro en perfil | Catálogo | Descripción |
|---------------------|----------|-------------|
| `encoding_code` | `CharsetEncoding` | Codificación del archivo (`utf-8`, `latin-1`, …). Incluye opción **Detección automática** (`auto`): File intake sugiere valor al subir muestra |
| `encoding_custom` | — | Reservado si el registro elegido permite valor propio (extensión futura) |
| `line_ending_code` | `LineEnding` | Final de línea: `lf`, `crlf`, **auto**, o **personalizado** |
| `line_ending_custom` | — | Secuencia o condición libre cuando `LineEnding.allows_custom_value` es true |

> Los listados **no están fijos en código**. El administrador define encodings y finales de línea en mantenimiento; el usuario solo selecciona en el Paso 1.

---

### Paso 2 — Línea de inicio de captura

El usuario define **desde qué línea** comienza la lectura de datos útiles.

| Modo | Código | Descripción | Ejemplo |
|------|--------|-------------|---------|
| Primera línea | `first` | Empieza en línea 1 | Archivo sin encabezado irrelevante |
| Línea específica | `line_number` | Número de línea 1-based | Línea 10 si las primeras 9 son metadata |
| Tras encabezado fijo | `after_header_block` | Saltar N líneas iniciales | `skip_lines: 3` (cabecera corporativa) |
| Tras patrón | `after_pattern` | Iniciar cuando una línea coincide con regex | `^REGISTRO\|` |
| Tras líneas en blanco | `after_blank_run` | Tras N líneas vacías (`not line.strip()`); inicia en la siguiente | `blank_count: 1` |
| Desde marcador de inicio | `marker_start` | Texto literal que indica inicio (`=== DATOS ===`) |

**Parámetro JSON:**

```json
"capture_start": {
  "mode": "line_number",
  "line": 10
}
```

```json
"capture_start": {
  "mode": "after_blank_run",
  "blank_count": 1
}
```

**Semántica `after_blank_run`:** línea vacía = `not line.strip()`. La captura empieza en la línea inmediata tras la N-ésima blanca consecutiva. Default `blank_count: 1`. Si no hay run suficiente, se mantiene el inicio por defecto (inicio del archivo / sin avance).
---

### Paso 3 — Línea de fin de captura

El usuario define **dónde termina** la lectura.

| Modo | Código | Descripción | Ejemplo |
|------|--------|-------------|---------|
| Final del archivo | `eof` | Hasta la última línea | Caso más común |
| Línea específica | `line_number` | Detener en línea N inclusive | Solo filas 10–500 |
| Porcentaje del archivo | `percent` | Procesar hasta X % de líneas totales | 80 % para pruebas parciales |
| Número máximo de filas | `max_rows` | Tras leer N filas de datos, parar | Primeras 1000 filas |
| Antes de patrón | `before_pattern` | Detener cuando aparece regex | `^TOTAL` en footer |
| Marcador de fin | `marker_end` | Detener al encontrar texto literal (`=== FIN ===`) |
| Líneas en blanco consecutivas | `blank_run` | Fin exclusive en la primera blanca del run de N vacías | `blank_count: 1` |
| Combinación | `line_or_eof` | Línea N o EOF, lo que ocurra primero |

**Parámetro JSON:**

```json
"capture_end": {
  "mode": "line_number",
  "line": 500
}
```

```json
"capture_end": {
  "mode": "percent",
  "value": 80
}
```

```json
"capture_end": {
  "mode": "blank_run",
  "blank_count": 1
}
```

**Semántica `blank_run`:** línea vacía = `not line.strip()`. Al encontrar N blancas consecutivas, el fin es **exclusive** en la primera blanca de ese run (las blancas no se incluyen). Default `blank_count: 1`. Si no hay run, se lee hasta EOF.

**Validación:** `capture_end` debe ser posterior a `capture_start` (misma unidad: líneas). `blank_count` ≥ 1.

**Archivo más corto que `capture_end.line` (política B+E):**

| Modo fin | Comportamiento |
|----------|----------------|
| `line_number` | Trunca a EOF y emite warning `CAPTURE_OUT_OF_RANGE` en el informe |
| `line_or_eof` | Trunca a EOF **sin** warning |

---

### Paso 4 — Definición de campos / columnas

El usuario especifica cada campo del origen. La forma depende del tipo de archivo (ver sección **Parámetros por tipo** más abajo).

#### Propiedades comunes de campo

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `name` | string | Sí | Identificador interno (slug, único) |
| `label` | string | No | Etiqueta visible |
| `content_type` | enum | Sí | Tipo de contenido esperado (ver tabla) |
| `required` | boolean | No | El campo no puede quedar vacío en la fila |
| `pattern` | string | No | Regex adicional de validación |

#### Tipos de contenido por campo (`content_type`)

| Código | Descripción | Validación |
|--------|-------------|------------|
| `alphanumeric` | Letras y números | `^[A-Za-z0-9]+$` (configurable) |
| `alpha` | Solo letras | `^[A-Za-z]+$` |
| `numeric` | Solo números | `^[0-9]+$` |
| `decimal` | Número con decimales | `^[0-9]+(\.[0-9]+)?$` |
| `alphanumeric_spaces` | Letras, números y espacios | Nómina, nombres con espacio |
| `date` | Fecha | Formato configurable (`DD/MM/YYYY`, `YYYYMMDD`, …) |
| `datetime` | Fecha y hora | Formato configurable |
| `free_text` | Texto libre | Sin restricción de charset |
| `custom` | Patrón propio | Usa `pattern` regex del usuario |

**Para `txt_fixed`:** cada campo define la posición con una de estas alternativas (UI paso 4):

| Modo UI | Propiedades | Descripción |
|---------|-------------|-------------|
| Inicio y fin | `start`, `end` | Posiciones 1-based inclusive |
| Inicio y longitud | `start`, `length` | `end = start + length - 1` |
| Desde carácter | `char` (± `start`/`length` opcionales) | El campo inicia a partir del marcador `char` en la línea |

| Propiedad | Descripción |
|-----------|-------------|
| `start` | Posición 1-based del primer carácter (cuando hay rango numérico) |
| `end` | Posición 1-based del último carácter (inclusive) |
| `length` | Alternativa a `end`: `end - start + 1` |
| `char` | Marcador literal de inicio en la línea |

Ejemplo: `documento` ocupa posiciones 1–5 → `start: 1`, `end: 5` (equivale a `length: 5`).

**Para `txt_delimited` / `csv`:** índice de columna o nombre de encabezado.

**Para `xlsx`:** letra de columna o nombre de encabezado en la hoja.

---

### Paso 5 — Reglas globales de contenido

Configuración a nivel de **archivo completo** o **línea**, aplicada antes o durante el parseo.

| Regla | Parámetro | Descripción |
|-------|-----------|-------------|
| Caracteres permitidos | `allowed_chars` | Whitelist global (ej. solo ASCII imprimible) |
| Caracteres excluidos | `excluded_chars` | Blacklist (ej. `\t`, `|`, caracteres de control) |
| Patrones prohibidos | `forbidden_patterns` | Lista de regex que invalidan una línea |
| Trimming global | `trim_lines` | boolean — quitar espacios al inicio/fin de cada línea |
| Líneas vacías | `skip_empty_lines` | boolean — ignorar líneas en blanco |
| Comentarios | `comment_prefix` | string — ignorar líneas que empiezan con `#`, `//`, etc. |

**Parámetro JSON:**

```json
"content_rules": {
  "trim_lines": true,
  "skip_empty_lines": true,
  "excluded_chars": ["\x00", "\x1a"],
  "comment_prefix": "#",
  "forbidden_patterns": ["^ERROR"]
}
```

**Comportamiento en parseo:** si una línea viola `forbidden_patterns` o contiene `excluded_chars`, se registra en el informe (Paso 6) y se aplica la política de error del proyecto (`skip_row` / `abort`).

---

### Paso 6 — Configuración del informe de procesamiento

El usuario indica **qué debe reportar** el sistema al procesar un archivo contra este perfil. La generación del informe ocurre en ejecución; aquí solo se define el contrato.

| Opción | Parámetro | Descripción |
|--------|-----------|-------------|
| Informe habilitado | `report_enabled` | boolean |
| Resumen OK | `include_summary` | Total filas leídas, procesadas, rechazadas |
| Detalle por fila | `include_row_errors` | Lista línea + campo + mensaje |
| Umbral de alerta | `reject_alert_threshold` | Avisar si rechazos > N o > X % |
| Formato de salida | `report_format` | `json`, `csv`, `html` (MVP: `json` + `csv`) |

**Contenido mínimo del informe:**

```json
{
  "status": "partial",
  "summary": {
    "rows_read": 1000,
    "rows_ok": 985,
    "rows_rejected": 15,
    "reject_rate_percent": 1.5
  },
  "messages": [
    {"level": "warning", "text": "15 registros no cumplieron con lo requerido"}
  ],
  "row_errors": [
    {"line": 42, "field": "salario", "code": "CONTENT_TYPE_MISMATCH", "value": "ABC"}
  ]
}
```

| `status` | Condición |
|----------|-----------|
| `ok` | Todas las filas válidas |
| `partial` | Al menos una fila rechazada, ejecución completada |
| `failed` | Abortado por política o error fatal |

---

## Parámetros por tipo

> Sección conservada y ampliada. Aplica al **Paso 4** según el tipo elegido en el Paso 1.

### `txt_fixed`

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `encoding_code` | string (FK catálogo) | Sí | `CharsetEncoding.code` — ver `TextReadFormat` |
| `line_ending_code` | string (FK catálogo) | No | `LineEnding.code` |
| `line_ending_custom` | string | Condicional | Si el catálogo permite valor personalizado |
| `capture_start` | object | Sí | Ver Paso 2 |
| `capture_end` | object | Sí | Ver Paso 3 |
| `content_rules` | object | No | Ver Paso 5 |
| `fields` | array | Sí | Lista de campos |

**Campo (`txt_fixed`):**

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `name` | string | Identificador interno (slug) |
| `label` | string | Etiqueta visible (opcional) |
| `start` | integer | Posición 1-based |
| `end` | integer | Posición 1-based inclusive (o usar `length`) |
| `length` | integer | Alternativa a `end` |
| `content_type` | enum | Ver Paso 4 |
| `date_format` | string | Si `content_type` es `date` / `datetime` |
| `required` | boolean | Campo obligatorio en la fila |

**Ejemplo (nómina legacy):**

```
12345JUAN      2500001
12346MARIA     1800002
```

| Campo | start | end | content_type |
|-------|-------|-----|--------------|
| documento | 1 | 5 | numeric |
| nombre | 6 | 15 | alpha |
| salario | 16 | 21 | numeric |
| estado | 22 | 22 | alphanumeric |

---

### `txt_delimited` / `csv`

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `encoding` | string | Sí | Codificación del archivo |
| `delimiter` | string | Sí | `;`, `,`, `\t`, `\|` |
| `quote_char` | string | No | `"` por defecto |
| `escape_char` | string | No | `\` si aplica |
| `has_header` | boolean | Sí | Primera fila de datos es encabezado |
| `header_row` | integer | No | Fila del encabezado (default 1, relativa a `capture_start`) |
| `capture_start` | object | Sí | Ver Paso 2 |
| `capture_end` | object | Sí | Ver Paso 3 |
| `content_rules` | object | No | Ver Paso 5 |
| `fields` | array | Condicional | Obligatorio si `has_header: false` |

**Campo (sin encabezado):**

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `name` | string | Identificador del campo |
| `column_index` | integer | Índice 0-based |
| `content_type` | enum | Ver Paso 4 |

**Campo (con encabezado):** se infiere del nombre de columna; el usuario puede renombrar `name` y asignar `content_type`.

---

### `xlsx`

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `sheet_name` | string | Sí | Hoja a leer |
| `header_row` | integer | No | Fila de encabezados (relativa a la hoja) |
| `capture_start` | object | Sí | Fila de inicio de datos (Paso 2) |
| `capture_end` | object | Sí | Fila de fin (Paso 3) |
| `content_rules` | object | No | Ver Paso 5 |
| `fields` | array | Condicional | Mapeo columna → nombre interno |

**Campo:**

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `name` | string | Identificador interno |
| `column` | string | Letra (`A`, `B`) o nombre de columna |
| `content_type` | enum | Ver Paso 4 |

---

## Modelo conceptual: `SourceProfile`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `project_version_id` | FK | Versión del proyecto |
| `type` | enum | `txt_fixed`, `txt_delimited`, `csv`, `xlsx`, … |
| `capture_start` | JSON | Paso 2 |
| `capture_end` | JSON | Paso 3 |
| `content_rules` | JSON | Paso 5 |
| `processing_report` | JSON | Paso 6 |
| `config` | JSON | Parámetros específicos del tipo (delimiter, sheet, encoding…) |
| `fields` | JSON | Lista normalizada de campos (Paso 4) |
| `created_at` | datetime | — |
| `updated_at` | datetime | — |

**Campo origen normalizado** (salida común a todos los tipos):

```json
{
  "name": "documento",
  "label": "Documento",
  "content_type": "numeric",
  "required": true,
  "source_meta": {
    "start": 1,
    "end": 5
  }
}
```

`source_meta` varía según el tipo; el motor y el mapeo consumen `name`, `label`, `content_type` y `required` de forma uniforme.

---

## Fragmento JSON completo (`source`)

```json
{
  "source": {
    "file_type_code": "txt_fixed",
    "encoding_code": "latin-1",
    "encoding_custom": null,
    "line_ending_code": "lf",
    "line_ending_custom": null,
    "capture_start": {"mode": "line_number", "line": 1},
    "capture_end": {"mode": "eof"},
    "content_rules": {
      "trim_lines": true,
      "skip_empty_lines": true,
      "excluded_chars": ["\x00"]
    },
    "processing_report": {
      "report_enabled": true,
      "include_summary": true,
      "include_row_errors": true,
      "reject_alert_threshold": 10,
      "report_format": "json"
    },
    "fields": [
      {
        "name": "documento",
        "label": "Documento",
        "start": 1,
        "end": 5,
        "content_type": "numeric",
        "required": true
      },
      {
        "name": "nombre",
        "label": "Nombre",
        "start": 6,
        "end": 15,
        "content_type": "alpha",
        "required": true
      },
      {
        "name": "salario",
        "label": "Salario",
        "start": 16,
        "end": 21,
        "content_type": "numeric",
        "required": true
      },
      {
        "name": "estado",
        "label": "Estado",
        "start": 22,
        "end": 22,
        "content_type": "alphanumeric",
        "required": false
      }
    ]
  }
}
```

---

## Validaciones al guardar

| Regla | Comportamiento |
|-------|----------------|
| Tipo de archivo seleccionado | **Error** si vacío (`strict`) |
| `capture_end` posterior a `capture_start` | **Error** cuando ambos modos exponen línea comparable (`first`, `line_number`, `after_header_block` vs `line_number` / `line_or_eof`) |
| `percent` / `max_rows` / `blank_count` | **Error** si fuera de rango (`percent` 1–100; `max_rows` ≥ 1; `blank_count` ≥ 1) |
| Campos sin solapamiento (`txt_fixed`) | **Error** si rangos numéricos se cruzan (campos solo-`char` no participan en solape) |
| `start` ≤ `end` / `length` ≥ 1 en posicional | **Error** |
| Alternativa posicional incompleta | **Error** si no hay `start`/`end`, `start`/`length` ni `char` |
| Al menos un campo definido | **Error** (`strict`) |
| Nombres de campo únicos | **Error** |
| `content_type: date`/`datetime` sin `date_format` | **Advertencia** (no bloquea guardar ni publicar) |
| `report_enabled: true` sin `include_summary` ni `include_row_errors` | **Advertencia** (no bloquea) |

**Canal UI:** errores → modal `error` / fallos de servicio; advertencias → modal `warning` o `messages.warning`. Textos: [`UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.8.

**Implementación:** `validate_source_dict(..., strict=)` en `apps/dms/source_profile/services/source_persistence_service.py` retorna `(errors, warnings)`.

---

## Estado de implementación (código)

| Pieza | Ubicación | Estado |
|-------|-----------|--------|
| Asistente 6 pasos + hub | `templates/dms/source_profile/`, `views.py` | MVP hecho |
| Persistencia borrador AJAX | `source_persistence_service.py`, `source_profile-persistence.js` | MVP hecho |
| Catálogos pasos 1–3, content types | `source_profile_catalog_service.py`, `apps/dms/catalogs/` | MVP hecho |
| Paso 4 `txt_fixed` / delimitado / `xlsx` / `json` / `xml` | templates + JS + parser | MVP hecho |
| Captura patrón / blancos (`after_*` / `before_*` / `blank_run`) | wizard + `capture_boundary_service.py` | MVP hecho |
| Normalización `source_meta` (`length`/`char`) | `field_normalization_service.py` | MVP hecho |
| Publicar versión | `version_publish_service.py` | MVP hecho |
| File intake / preview | `apps/dms/file_intake/` | MVP hecho |
| Motor parseo + informe | `apps/dms/transform_execution/` | MVP hecho |

---

## Errores de validación por campo (en ejecución)

Códigos estables; el texto `message` del informe se localiza desde `ExecutionErrorCode` (ver [`system_catalogs.md`](system_catalogs.md) §7 y `execution_error_catalog_service.py`).

| Código | Descripción |
|--------|-------------|
| `CONTENT_TYPE_MISMATCH` | Valor no cumple `content_type` |
| `REQUIRED_FIELD_EMPTY` | Campo obligatorio vacío |
| `PATTERN_MISMATCH` | No cumple regex `pattern` |
| `FORBIDDEN_CHAR` | Carácter en `excluded_chars` |
| `FORBIDDEN_PATTERN` | Coincide con `forbidden_patterns` |
| `LINE_LENGTH_MISMATCH` | Línea más corta que definición posicional |
| `DELIMITER_MISMATCH` | Columnas inconsistentes |
| `CAPTURE_OUT_OF_RANGE` | Línea de captura fuera de rango (warning; p. ej. archivo corto vs `line_number`) |

---

## Detección automática (módulo File intake — referencia)

La auto-detección de encoding, tipo y delimitador **no forma del núcleo de definición**; vive en el módulo de carga de archivo muestra y solo **sugiere valores** para los pasos 1–4.

| Señal | Heurística |
|-------|------------|
| Extensión `.xlsx` / `.xls` | Tipo `xlsx` |
| Extensión `.csv` | Tipo `csv`; delimitador `,` vs `;` |
| Extensión `.txt` | Longitud constante → `txt_fixed`; separador → `txt_delimited` |
| Encoding | `chardet` + fallback `utf-8` |

> **Documentado en:** [`file_intake.md`](file_intake.md).

---

## Casos de uso

### SD-01 — Inicio en línea 10 por encabezado corporativo

| | |
|---|---|
| **Actor** | Diseñador |
| **Flujo** | Paso 1: `txt_fixed` → Paso 2: línea 10 → Paso 3: `eof` → Paso 4: campos posicionales → guardar |
| **Resultado** | Ignora las 9 primeras líneas en cada ejecución |

### SD-02 — Captura hasta el 80 % del archivo

| | |
|---|---|
| **Actor** | Integrador en pruebas |
| **Flujo** | Paso 3: modo `percent`, valor 80 → define campos CSV → informe habilitado |
| **Resultado** | Solo procesa porción inicial; útil para validación sin archivo completo |

### SD-03 — Campos con tipo numérico y alfabético

| | |
|---|---|
| **Actor** | Analista de nómina |
| **Flujo** | Define `documento` numeric, `nombre` alpha, `salario` numeric → informe con `rows_rejected` |
| **Resultado** | Filas con `nombre` numérico aparecen en informe como `CONTENT_TYPE_MISMATCH` |

### SD-04 — Exclusión de caracteres de control

| | |
|---|---|
| **Actor** | Operador |
| **Flujo** | Paso 5: `excluded_chars` incluye `\x00`, `\x1a` → ejecuta archivo |
| **Resultado** | Líneas con esos caracteres en informe de rechazo |

### SD-05 — CSV con separador `;` y fin en línea 500

| | |
|---|---|
| **Actor** | Integrador |
| **Flujo** | `csv`, delimitador `;`, `capture_end: line 500`, encabezado fila 1 |
| **Resultado** | Procesa bloque acotado con columnas nombradas |

---

## Pendiente de definir / futuro

- [x] Documento `file_intake.md` — upload, preview, selección archivo producción
- [x] UI: asistente de **6 pasos** + hub (decisión: no pantalla única)
- [x] ¿`end` inclusive vs exclusive? — **decisión: inclusive** (posición último carácter)
- [x] Alternativas posicionales `length` / `char` en UI y validación
- [x] Semántica advertencia vs error (`date_format`, informe) según § Validaciones
- [x] Validación cruzada captura inicio/fin para modos MVP comparables
- [x] Modos `after_pattern` / `before_pattern` (UI + motor)
- [x] Modos `after_blank_run` / `blank_run` (UI + motor; vacío = `not line.strip()`;
  start tras N-ésima blanca; end exclusive en primera blanca del run; `blank_count` default 1)
- [x] Localización de mensajes del informe
  (`ExecutionErrorCode.description`/`name` vía `execution_error_catalog_service` en `build_report_data` / dry-run)
- [x] Comportamiento si archivo producción tiene menos líneas que `capture_end.line`
  (`line_number` → truncar a EOF + warning `CAPTURE_OUT_OF_RANGE`; `line_or_eof` → truncar sin warning)

---

## Fase

| Alcance | Fase | Código |
|---------|------|--------|
| Pasos 1–6 para `txt_fixed`, `csv`, `txt_delimited`, `xlsx`, `json`, `xml` | MVP | Hecho |
| `content_type` + informe JSON/CSV (contrato) | MVP | Hecho |
| Marcadores `marker_start` / `marker_end` (semilla MVP) | MVP | Hecho (UI + catálogo) |
| Modos de captura por **patrón** (`after_pattern`, `before_pattern`) | MVP | Hecho (UI + motor) |
| Modos por **líneas en blanco** (`after_blank_run`, `blank_run`) | MVP | Hecho (UI + motor) |
| Localización mensajes informe (`ExecutionErrorCode`) | MVP | Hecho |
| Política archivo corto vs `capture_end.line` (B+E) | MVP | Hecho |
| `json`, `xml` como tipo de origen | MVP | Hecho (UI + parser; semilla `mvp`) |

> Nota: patrones y blancos están en semilla **mvp** y habilitados en el asistente.
---

## Documentos relacionados (DMS)

| Documento | Contenido |
|---------|-----------|
| [`DataMappingStudio.md`](../DataMappingStudio.md) | Visión general |
| [`dms_integration.md`](dms_integration.md) | Tenant, modelos Django |
| [`source_definition.md`](source_definition.md) | Este documento |
| [`system_catalogs.md`](system_catalogs.md) | Catálogos `SourceFileType`, `TextReadFormat`, `CaptureBoundaryMode`, … |
| [`file_intake.md`](file_intake.md) | Carga, preview, archivo a procesar |
| [`transform_execution.md`](transform_execution.md) | Ejecución, descarga, historial |
| [`project_lifecycle.md`](project_lifecycle.md) | Contenedor del proyecto, permisos, publicar versión |
| [`target_definition.md`](target_definition.md) | Definición destino (Módulo 4) |
| [`field_mapping.md`](field_mapping.md) | Mapeo origen ↔ destino |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Catálogo mensajes (§3.8 SourceProfile) |
| [`../definition_app/CONVENCIONES.md`](../definition_app/CONVENCIONES.md) | Convenciones Django / servicios |
