# Target definition

Proceso y especificación del **Módulo 4** de Data Mapping Studio: definir cómo debe generarse el archivo de salida y persistir esa configuración como `TargetProfile`.

> Estado: **MVP implementado** (asistente 6 pasos, borrador sincronizado con `DmsMappingVersion`, variantes `txt_fixed` / delimitado / `xlsx` / `json` / `xml`).  
> Publicación de versión valida origen **y** destino (strict).  
> Pendiente: plantillas de TargetProfile por industria.  
> Plataforma: [`dms_integration.md`](dms_integration.md).  
> Mensajes UI: [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.8.  
> Espejo de estructura: [`source_definition.md`](source_definition.md).

---

## Propósito

Permitir que el usuario configure **paso a paso** la estructura y reglas del archivo que el sistema debe **producir** tras mapear y transformar los datos de origen.

El resultado es un `TargetProfile` reutilizable: el motor lo usa en la fase de serialización (después del mapeo y las reglas de transformación).

Sin un perfil de destino válido, no hay esquema contra el cual validar ni formato concreto para escribir el archivo de salida.

---

## Relación con otros módulos

```mermaid
flowchart LR
    Source[SourceProfile]
    Map[Field mapping]
    Rules[Transform rules]
    Target[TargetProfile]
    Engine[Motor serializacion]
    Source --> Map
    Map --> Rules
    Rules --> Target
    Target --> Engine
```

| Módulo | Rol |
|--------|-----|
| **Source definition** | Define cómo **leer** el archivo de entrada |
| **Field mapping** | Relaciona campos origen → campos destino |
| **Transform rules** | Modifica valores antes de escribir — [`transform_rules.md`](transform_rules.md) |
| **Target definition** | Define cómo **escribir** el archivo de salida |
| **File intake / execution** | Ejecuta el pipeline y entrega el archivo generado |

Los **campos destino** definidos aquí son la lista maestra a la que apunta el mapeo (`target_field`).

---

## Alcance de este documento

| Incluido | Excluido |
|----------|----------|
| Tipo de archivo de salida | Lectura del archivo origen |
| Encoding y final de línea de salida | Mapeo origen → destino |
| Layout del archivo (encabezado, delimitador, hoja, JSON/XML) | Reglas de transformación |
| Definición y validación de campos destino | Ejecución, dry run ni descarga |
| Reglas de serialización (padding, truncado, orden) | Historial de ejecuciones |
| Política ante valores inválidos en escritura | Informe de procesamiento origen (→ `SourceProfile`) |
| Modelo `TargetProfile` y JSON | |

---

## Responsabilidades

| Sí | No |
|----|-----|
| Asistente paso a paso de definición del destino | Parsear archivo de entrada |
| Esquema de campos que recibirán datos mapeados | Definir reglas `upper`, `date_format`, etc. |
| Validación de tipo, longitud y obligatoriedad **al escribir** | Ejecutar el job ni generar bytes finales |
| Reglas de formato posicional (padding, alineación) | Seleccionar archivo origen a procesar |
| Persistencia de `TargetProfile` | |

---

## Proceso de definición (asistente paso a paso)

El usuario recorre **6 pasos** en orden. Cada paso persiste borrador; puede volver atrás sin perder datos.

```mermaid
flowchart LR
    T1[Paso 1 Tipo salida]
    T2[Paso 2 Encoding salida]
    T3[Paso 3 Layout archivo]
    T4[Paso 4 Campos destino]
    T5[Paso 5 Serializacion]
    T6[Paso 6 Validacion escritura]
    Save[Guardar TargetProfile]
    T1 --> T2 --> T3 --> T4 --> T5 --> T6 --> Save
```

---

### Paso 1 — Tipo de archivo de salida

El sistema muestra los tipos habilitados desde el catálogo **`TargetFileType`** (mantenimiento con listado y CRUD — ver `system_catalogs.md`). Espejo de `SourceFileType`, orientado a **escritura**.

| Campo en perfil | Origen |
|-----------------|--------|
| `file_type_code` | `TargetFileType.code` seleccionado |
| Parámetros del asistente | `TargetFileType.config_schema` |

**Tipos previstos en datos semilla (referencia inicial, administrables):**

| Código | Nombre | Fase |
|--------|--------|------|
| `txt_fixed` | TXT posicional | MVP |
| `txt_delimited` | TXT delimitado | MVP |
| `csv` | CSV | MVP |
| `xlsx` | Excel | MVP |
| `json` | JSON | MVP |
| `xml` | XML | MVP |

> Los tipos no están fijos en código. El administrador los mantiene en catálogo.

---

### Paso 2 — Codificación y final de línea de salida

Parámetros de **escritura** del archivo generado. Reutiliza el catálogo **`TextReadFormat`** (`CharsetEncoding` + `LineEnding` en `system_catalogs.md`) — mismos valores, distinto contexto (salida vs entrada).

| Parámetro en perfil | Catálogo | Descripción |
|---------------------|----------|-------------|
| `encoding_code` | `CharsetEncoding` | Codificación del archivo generado |
| `encoding_custom` | — | Valor propio si aplica |
| `line_ending_code` | `LineEnding` | Final de línea en salida (`lf`, `crlf`, personalizado) |
| `line_ending_custom` | — | Secuencia libre si el catálogo lo permite |

En destino **no** suele usarse detección automática: el usuario elige explícitamente qué espera el sistema receptor. La opción `auto` puede ocultarse en este paso (solo encodings/line endings concretos).

---

### Paso 3 — Layout del archivo

Estructura global del archivo de salida según el tipo elegido.

#### Común a todos los tipos

| Parámetro | Descripción |
|-----------|-------------|
| `output_filename_pattern` | Patrón del nombre al **descargar** (no carpeta servidor). Ej: `nomina_{date:%Y%m%d}.csv` — ver `transform_execution.md` |
| `include_bom` | boolean — BOM UTF-8 al inicio (algunos sistemas legacy lo exigen) |

#### Por tipo

| Tipo | Parámetros layout |
|------|-------------------|
| `txt_fixed` | `record_length` opcional — longitud total de línea; `trailing_newline` — línea vacía al final |
| `txt_delimited` / `csv` | `delimiter`, `quote_char`, `escape_char`, `include_header` (boolean), `header_labels` (array o derivado de campos) |
| `xlsx` | `sheet_name`, `include_header`, `freeze_header_row`, `column_width_auto` |
| `json` | `root_type` (`array` \| `object`), `records_path` (ej. `$.records`), `pretty_print`, `indent` |
| `xml` | `root_element`, `record_element`, `namespace`, `declaration` (sí/no) |

**Encabezado de columnas (`include_header`):**

| Valor | Comportamiento |
|-------|----------------|
| `true` | Primera fila con `label` o `name` de cada campo destino |
| `false` | Solo datos desde la primera fila |

**Parámetro JSON (ejemplo CSV):**

```json
"layout": {
  "delimiter": ",",
  "quote_char": "\"",
  "include_header": true,
  "output_filename_pattern": "nomina_{date:%Y%m%d}.csv"
}
```

---

### Paso 4 — Definición de campos destino

Lista maestra de columnas/elementos que el archivo de salida contendrá. El **field mapping** enlazará campos origen a estos `name`.

#### Propiedades comunes de campo destino

| Propiedad | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `name` | string | Sí | Identificador interno (slug, único). Usado en mapeo |
| `label` | string | No | Encabezado visible (CSV/Excel) o etiqueta XML/JSON |
| `data_type` | enum | Sí | Tipo al serializar (ver tabla) |
| `required` | boolean | No | Si true: fila rechazada o política del Paso 6 si vacío |
| `max_length` | integer | Condicional | Obligatorio en `txt_fixed`; opcional en delimitados |
| `order` | integer | Sí | Orden de columna en salida |
| `default_value` | string | No | Valor si el mapeo no aporta dato |
| `pattern` | string | No | Regex de validación previa a escribir |

#### Tipos de dato destino (`data_type`)

| Código | Descripción | Serialización |
|--------|-------------|---------------|
| `string` | Texto | Tal cual, con escape según formato |
| `integer` | Entero | Sin decimales |
| `decimal` | Decimal | Separador configurable |
| `date` | Fecha | Formato en `date_format` |
| `datetime` | Fecha y hora | Formato en `datetime_format` |
| `boolean` | Sí/No | `true`/`false`, `1`/`0`, `S`/`N` (configurable) |

#### Por tipo de archivo

**`txt_fixed` — posición y longitud:**

| Propiedad | Descripción |
|-----------|-------------|
| `start` | Posición 1-based |
| `end` | Posición inclusive (o `length`) |
| `align` | `left` \| `right` |
| `pad_char` | Carácter de relleno (default espacio) |

**`txt_delimited` / `csv` — orden de columna:**

| Propiedad | Descripción |
|-----------|-------------|
| `order` | Índice de columna en la fila de salida |
| `quote` | boolean — forzar entrecomillado |

**`xlsx`:**

| Propiedad | Descripción |
|-----------|-------------|
| `column` | Letra o índice |
| `excel_type` | `general`, `text`, `number`, `date` |

**`json` / `xml`:**

| Propiedad | Descripción |
|-----------|-------------|
| `path` | Ruta del campo (`id`, `empleado.nombre`, XPath) |

**Ejemplo campos (CSV destino desde nómina TXT):**

| order | name | label | data_type | required |
|-------|------|-------|-----------|----------|
| 1 | documento | documento | string | true |
| 2 | nombre | nombre | string | true |
| 3 | salario | salario | integer | true |

---

### Paso 5 — Reglas de serialización

Cómo formatear valores al escribir cada campo. Aplica **después** del mapeo y transformación.

| Regla | Parámetro | Descripción |
|-------|-----------|-------------|
| Relleno izquierda | `pad_left` | char + longitud (`txt_fixed`) |
| Relleno derecha | `pad_right` | char + longitud |
| Truncar | `truncate` | `left` \| `right` \| `error` si supera `max_length` |
| Formato fecha salida | `date_format` | Ej: `YYYY-MM-DD` |
| Formato decimal | `decimal_places` | N decimales |
| Separador decimal | `decimal_separator` | `.` o `,` |
| Booleano como | `boolean_format` | `true_false`, `1_0`, `si_no` |
| Valor nulo | `null_representation` | `""`, `"NULL"`, omitir campo (JSON) |
| Trim antes de escribir | `trim_before_write` | boolean |

**Parámetro JSON:**

```json
"serialization": {
  "trim_before_write": true,
  "default_truncate": "right",
  "date_format": "YYYY-MM-DD",
  "boolean_format": "1_0",
  "null_representation": ""
}
```

Reglas por campo (opcional, sobreescriben globales):

```json
{
  "name": "salario",
  "serialization": {
    "pad_left": {"char": "0", "length": 8},
    "truncate": "error"
  }
}
```

---

### Paso 6 — Política de validación al escribir

Qué hace el motor cuando un valor **no cumple** el esquema destino antes de serializar.

| Política | Código | Descripción |
|----------|--------|-------------|
| Rechazar fila | `reject_row` | No escribe la fila; registra en informe de ejecución |
| Abortar job | `abort` | Detiene toda la ejecución |
| Truncar y escribir | `truncate` | Ajusta al `max_length` y continúa |
| Valor por defecto | `use_default` | Usa `default_value` del campo |
| Escribir vacío | `write_empty` | Deja campo vacío y continúa |

**Validaciones evaluadas:**

| Validación | Momento |
|------------|---------|
| Campo obligatorio vacío | Pre-escritura |
| Longitud > `max_length` (`txt_fixed`) | Pre-escritura |
| Tipo incompatible (`integer` con texto) | Pre-escritura |
| Patrón regex no cumplido | Pre-escritura |
| Suma de campos > `record_length` (`txt_fixed`) | Al guardar perfil |

**Parámetro JSON:**

```json
"write_validation": {
  "policy": "reject_row",
  "on_type_mismatch": "reject_row",
  "on_length_exceeded": "truncate",
  "on_required_empty": "reject_row"
}
```

---

## Parámetros por tipo

> Aplica a los pasos 3–5 según el tipo del Paso 1.

### `txt_fixed`

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `encoding_code` | Sí | Salida |
| `line_ending_code` | Sí | Salida |
| `layout.record_length` | No | Longitud fija de cada línea |
| `layout.trailing_newline` | No | Nueva línea al cierre del archivo |
| `fields[]` | Sí | Con `start`, `end`, `align`, `pad_char`, `max_length` |
| `serialization` | No | Reglas globales |
| `write_validation` | Sí | Política Paso 6 |

**Ejemplo línea generada:**

```
12345     JUAN      250000
```

| Campo | start | end | align | pad_char |
|-------|-------|-----|-------|----------|
| documento | 1 | 5 | right | `0` |
| nombre | 6 | 15 | left | ` ` |
| salario | 16 | 21 | right | `0` |

---

### `txt_delimited` / `csv`

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `encoding_code` | Sí | — |
| `line_ending_code` | Sí | — |
| `layout.delimiter` | Sí | `,` o `;` |
| `layout.include_header` | Sí | — |
| `layout.quote_char` | No | Default `"` |
| `fields[]` | Sí | Con `order`, `data_type` |
| `write_validation` | Sí | — |

---

### `xlsx`

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `layout.sheet_name` | Sí | Nombre de hoja |
| `layout.include_header` | Sí | — |
| `fields[]` | Sí | Con `order`, `column`, `excel_type` |
| `write_validation` | Sí | — |

---

### `json`

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `layout.root_type` | Sí | `array` de registros u `object` |
| `layout.records_path` | No | Ruta al arreglo de registros (vacío = raíz) |
| `layout.pretty_print` | No | Indentación legible |
| `layout.indent` | No | Espacios de indentación (default 2) |
| `fields[]` | Sí | Con `path` por campo |
| `write_validation` | Sí | — |

---

### `xml`

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `layout.root_element` | Sí | Elemento raíz |
| `layout.record_element` | Sí | Elemento por fila |
| `layout.namespace` | No | Namespace opcional |
| `layout.declaration` | No | Incluir declaración XML |
| `fields[]` | Sí | Con `path` (elemento hijo) por campo |
| `write_validation` | Sí | — |

---

## Modelo conceptual: `TargetProfile`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | PK |
| `project_version_id` | FK | Versión del proyecto |
| `file_type_code` | string | `TargetFileType.code` |
| `encoding_code` | string | Paso 2 |
| `line_ending_code` | string | Paso 2 |
| `layout` | JSON | Paso 3 |
| `fields` | JSON | Paso 4 |
| `serialization` | JSON | Paso 5 — reglas globales |
| `write_validation` | JSON | Paso 6 |
| `created_at` / `updated_at` | datetime | — |

**Campo destino normalizado:**

```json
{
  "name": "documento",
  "label": "documento",
  "data_type": "string",
  "required": true,
  "order": 1,
  "max_length": 10,
  "target_meta": {
    "start": 1,
    "end": 10,
    "align": "right",
    "pad_char": "0"
  }
}
```

`target_meta` varía según tipo; el mapeo solo requiere `name` estable.

---

## Fragmento JSON completo (`target`)

```json
{
  "target": {
    "file_type_code": "csv",
    "encoding_code": "utf-8",
    "line_ending_code": "crlf",
    "layout": {
      "delimiter": ",",
      "quote_char": "\"",
      "include_header": true,
      "output_filename_pattern": "nomina_{date:%Y%m%d}.csv"
    },
    "serialization": {
      "trim_before_write": true,
      "date_format": "YYYY-MM-DD",
      "null_representation": ""
    },
    "write_validation": {
      "policy": "reject_row",
      "on_type_mismatch": "reject_row",
      "on_length_exceeded": "truncate",
      "on_required_empty": "reject_row"
    },
    "fields": [
      {
        "name": "documento",
        "label": "documento",
        "data_type": "string",
        "required": true,
        "order": 1,
        "max_length": 20
      },
      {
        "name": "nombre",
        "label": "nombre",
        "data_type": "string",
        "required": true,
        "order": 2,
        "max_length": 50
      },
      {
        "name": "salario",
        "label": "salario",
        "data_type": "integer",
        "required": true,
        "order": 3
      }
    ]
  }
}
```

---

## Validaciones al guardar

| Regla | Comportamiento |
|-------|----------------|
| Tipo de archivo seleccionado | Error si vacío |
| Al menos un campo destino | Error |
| Nombres de campo únicos | Error |
| `order` único por campo (delimitados) | Error si duplicado |
| Campos sin solapamiento (`txt_fixed`) | Error |
| `start` ≤ `end`; suma coherente con `record_length` | Error o advertencia |
| Campo `required` sin `default_value` y política `use_default` | Advertencia |
| `delimiter` vacío en CSV | Error |
| `sheet_name` vacío en Excel | Error |

---

## Errores en ejecución (pre-escritura)

| Código | Descripción |
|--------|-------------|
| `TARGET_REQUIRED_EMPTY` | Campo obligatorio sin valor |
| `TARGET_TYPE_MISMATCH` | Valor no convertible a `data_type` |
| `TARGET_LENGTH_EXCEEDED` | Supera `max_length` y política no permite truncar |
| `TARGET_RECORD_LENGTH_OVERFLOW` | Línea posicional excede `record_length` |
| `TARGET_PATTERN_MISMATCH` | No cumple regex del campo |
| `TARGET_SERIALIZATION_ERROR` | Fallo al formatear (fecha inválida, etc.) |

---

## Consideraciones de diseño

| Tema | Decisión propuesta |
|------|-------------------|
| Origen vs destino | Perfiles independientes (`SourceProfile` + `TargetProfile`); el proyecto los une |
| Campos destino antes del mapeo | El asistente destino puede completarse antes o después del mapeo; el mapeo solo ofrece destinos ya definidos |
| Mismo catálogo encoding/line ending | Reutilizar `TextReadFormat` para salida; UI del Paso 2 destino oculta `auto` |
| Catálogo tipos salida | `TargetFileType` espejo de `SourceFileType` — mantenimiento separado (lectura ≠ escritura) |
| Preview de salida | Vista previa de línea/columna generada en módulo dry run, no en este asistente |
| Campos calculados / generados | Constantes, concat y generadores en `field_mapping.md`; aquí solo esquema físico del campo |
| UTF-8 por defecto en CSV moderno | Semilla recomienda `utf-8` + `crlf` o `lf` según sistema receptor |

---

## Casos de uso

### TD-01 — TXT posicional legacy para mainframe

| | |
|---|---|
| **Actor** | Integrador |
| **Flujo** | Paso 1: `txt_fixed` → campos con posiciones y `pad_left` en IDs → política `truncate` en longitud |
| **Resultado** | `TargetProfile` listo para serializar hacia mainframe |

### TD-02 — CSV con encabezado para carga RRHH

| | |
|---|---|
| **Actor** | Analista |
| **Flujo** | Paso 1: `csv` → UTF-8 → delimitador `,` → `include_header: true` → 3 campos con `order` |
| **Resultado** | CSV estándar con cabecera `documento,nombre,salario` |

### TD-03 — Excel con hoja nombrada

| | |
|---|---|
| **Actor** | Usuario de negocio |
| **Flujo** | `xlsx`, hoja «Export», encabezados visibles, columnas texto para IDs |
| **Resultado** | `.xlsx` con formato listo para revisión manual |

### TD-04 — Rechazo de filas con salario inválido

| | |
|---|---|
| **Actor** | Diseñador |
| **Flujo** | Campo `salario` `integer`, `required`, política `reject_row` en tipo incorrecto |
| **Resultado** | Filas inválidas en informe; no corrompen el archivo destino |

### TD-05 — Alineación con mapeo existente

| | |
|---|---|
| **Actor** | Diseñador |
| **Precondición** | Mapeo `documento` → `documento`, `nombre` → `nombre` |
| **Flujo** | Define campos destino con mismos `name` que referencias del mapeo |
| **Resultado** | Pipeline origen → mapeo → destino coherente |

---

## Estado de implementación (código)

| Pieza | Ubicación | Estado |
|-------|-----------|--------|
| Asistente 6 pasos + hub | `templates/dms/target_profile/`, `views.py` | MVP hecho |
| Persistencia borrador AJAX | `target_persistence_service.py`, `target_profile-persistence.js` | MVP hecho |
| Catálogos pasos 1–2 / `data_type` | `target_profile_catalog_service.py` | MVP hecho |
| Paso 4 fixed / delimitado / xlsx / json / xml | templates + `target_profile-fields*.js` | MVP hecho |
| Normalización `target_meta` | `field_normalization_service.py` | MVP hecho |
| Publicar (valida origen+destino) | `version_publish_service.py` | MVP hecho |
| Serialización runtime `json` / `xml` / `xlsx` | `target_serializer_service.py` | Hecho |

---

## Pendiente de definir / futuro

- [x] Catálogo `TargetFileType` en `system_catalogs.md` (mantenimiento + semilla)
- [x] Reutilizar `TextReadFormat` (CharsetEncoding / LineEnding) sin `auto` en paso 2
- [x] UI: asistente **6 pasos** paralelo a origen (origen → destino → mapeo)
- [x] MVP pasos 1–6 `txt_fixed` / `csv` / `txt_delimited` / `xlsx`
- [x] Editor layout + campos `json` / `xml`
- [x] Serialización runtime `json` / `xml`
- [x] Serialización runtime `xlsx`
- [ ] Plantillas de `TargetProfile` por industria
- [x] Validación cruzada: campos mapeados sin definición en destino (tras field mapping)

---

## Fase

| Alcance | Fase | Código |
|---------|------|--------|
| Pasos 1–6 para `txt_fixed`, `csv`, `txt_delimited`, `xlsx` | MVP | Hecho |
| `write_validation` + serialización texto (contrato) | MVP | Hecho |
| Catálogo `TargetFileType` + semilla | MVP | Hecho |
| Editor `json` / `xml` (layout + campos) | MVP | Hecho |
| Serialización runtime `json` / `xml` | MVP | Hecho |
| Serialización runtime `xlsx` | MVP | Hecho |

---

## Documentos relacionados (DMS)

| Documento | Contenido |
|---------|-----------|
| [`DataMappingStudio.md`](../DataMappingStudio.md) | Visión general — Módulo 4 |
| [`source_definition.md`](source_definition.md) | Definición origen (espejo de estructura) |
| [`target_definition.md`](target_definition.md) | Este documento |
| [`system_catalogs.md`](system_catalogs.md) | `TargetFileType`, `TextReadFormat`, `TargetFieldDataType` |
| [`project_lifecycle.md`](project_lifecycle.md) | Contenedor del proyecto y permisos |
| [`field_mapping.md`](field_mapping.md) | Enlace origen ↔ destino |
| [`file_intake.md`](file_intake.md) | Upload archivo producción |
| [`transform_execution.md`](transform_execution.md) | Serialización runtime, descarga |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Mensajes UI (§3.8) |
| [`dms_integration.md`](dms_integration.md) | Modelos / tenant |
