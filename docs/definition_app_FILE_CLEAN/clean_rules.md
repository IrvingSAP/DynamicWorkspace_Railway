# Módulo 3 — Reglas de limpieza (FILE CLEAN)

> **App:** File Clean  
> **Estado:** borrador de definición  
> **Reuso:** motor de reglas FilePipe / DMS (sin fork de pipeline ETL)

---

## Objetivo

Mantener un **catálogo ordenado** de reglas de limpieza aplicables al perfil de lectura, editables en borrador y congeladas al publicar.

---

## Principios

1. **Explícitas** — nada se limpia si no hay regla.  
2. **Ordenadas** — el orden de aplicación es parte del contrato.  
3. **Auditables** — cada aplicación produce entrada en el change log del job.  
4. **Compartidas** — mismas implementaciones que DMS cuando el `code` exista; Clean solo filtra el subset “limpieza”.

---

## Modelo de una regla

| Campo | Descripción |
|-------|-------------|
| `code` | Identificador (`trim`, `case_upper`, `date_normalize`, …) |
| `field_name` | Null = global; si no, campo del perfil |
| `params` | JSON (formato fecha, mapa replace, plantilla compose, clave dedupe…) |
| `enabled` | Bool |
| `sort_order` | Entero |

---

## Catálogo MVP (subset)

Ver tabla resumen en [`../FILE_CLEAN.md`](../FILE_CLEAN.md) §8. Prioridad de implementación:

| Prioridad | Codes |
|-----------|--------|
| P0 | `trim`, `strip_invisible`, `case_upper`, `case_lower`, `null_tokens` |
| P1 | `date_normalize`, `number_normalize`, `replace_map`, `replace` |
| P2 | `compose`, `dedupe_rows`, `encoding_normalize` |

---

## Semántica: `replace_map`, `replace`, `compose`

### `replace_map` — valor completo (match exacto)

Sustituye el **valor entero** del campo solo si coincide **exactamente** con una clave del mapa. No busca ni reemplaza fragmentos dentro del string.

| Aspecto | Contrato |
|---------|----------|
| Params | `map`: objeto `{ "<from>": "<to>", … }` |
| Match | Exacto; **case-sensitive** por defecto |
| Opcional | `case_insensitive`: bool (default `false`) |
| Sin match | El valor **no cambia** (no error) |
| Vacío | `""` solo se reemplaza si existe clave `""` en `map` (distinto de `null_tokens`) |
| Reuso | Misma semántica que DMS `replace_map` |

Ejemplo: `M` → `Masculino`; `F` → `Femenino`. El valor `Mas` **no** coincide con `M`.

### `replace` — porción dentro del string

Busca un fragmento **dentro** del valor del campo y lo sustituye. Reutiliza el `code` DMS `replace` (no inventar otro nombre).

| Aspecto | Contrato MVP |
|---------|----------------|
| Params | `find` (requerido), `replace` (string; puede ser `""`) |
| `find` vacío | **Error** al guardar / publicar |
| Alcance | `all`: bool — todas las ocurrencias (`true`) o solo la primera (`false`). Default MVP: `true` |
| Case | `ignore_case`: bool (default `false`) |
| Regex | **No** en MVP Clean; flag `regex` → Fase 2 (opt-in; riesgo DoS / UI) |
| Reuso | Alineado a DMS `replace` (`find`, `replace`, futuro `regex`) |

Ejemplo: `find: "-"`, `replace: ""` en RUT `12-345` → `12345`.

### `compose` — plantilla (literal + valor + campo + secuencia)

Una sola op flexible en lugar de tres modos sueltos (“solo contador”, “literal+contador”, “literal+otro campo”). Reescribe el valor del campo según una plantilla con tokens.

| Aspecto | Contrato |
|---------|----------|
| Params | `template` (string requerido); opcionales de secuencia (abajo) |
| Frontera | Excepción documentada del subset “limpieza pura”; no sustituye mapeo N:1 de FilePipe |
| Expresiones libres | **Prohibidas** (sin sandbox / eval) |

#### Tokens MVP

| Token | Efecto |
|-------|--------|
| Texto literal | Se copia tal cual (fuera de `{…}`) |
| `{value}` | Valor actual del campo al que aplica la regla |
| `{field:<name>}` | Valor de otro campo de la **misma fila** (nombre del perfil) |
| `{seq}` | Contador del job (ver abajo) |

Ejemplos:

- Solo contador: `template: "{seq}"`  
- Literal + contador: `template: "LOT-{seq}"`  
- Literal + valor: `template: "ID-{value}"`  
- Literal + otro campo: `template: "REF-{field:codigo}"`

#### Secuencia `{seq}`

| Decisión | Contrato MVP |
|----------|----------------|
| Ámbito | **Por job** (un contador por ejecución) |
| Reinicio | Cada run arranca en `start` |
| Orden | Orden estable de filas del reader |
| Params | `seq_start` (default `1`), `seq_step` (default `1`), `seq_width` (padding; opcional), `seq_pad_char` (default `"0"`) |
| Concurrencia | Un job = un contador; sin secuencia compartida entre jobs/compañías en MVP |
| Change log | Registrar valor generado (FC2) |

#### Tokens / ops en Fase 2

- `{field:<name>:<start>,<len>}` — porción de otro campo  
- Op `substring` sobre el mismo campo (reuso DMS)  
- `regex` en `replace`

#### Dependencias entre campos

Si `compose` usa `{field:X}`, el orden de reglas **entre campos** debe ser determinista (mismo `sort_order` global del pipeline del proyecto). Documentar en UI que el valor de `X` es el **ya transformado** por reglas anteriores sobre `X`, o el bruto si aún no hubo reglas — política: **valor tras reglas ya aplicadas a esa fila en orden global**.

---

## Solapes a vigilar

| Par | Nota |
|-----|------|
| `null_tokens` vs `replace_map` con clave `""` | Preferir `null_tokens` para vacíos/sentinels; `replace_map` para códigos de negocio |
| `replace` vs `replace_map` | Fragmento vs valor completo; no intercambiables |
| `compose` vs FilePipe `concat` / `generated` | Clean: mismo esquema de lectura; Pipe: destino de negocio |

---

## Validaciones al guardar (borrador) y al publicar

Misma lógica de params; al **guardar** regla individual se valida esa fila; al **publicar** se revalida todo el pipeline (P5 en [`clean_publish.md`](clean_publish.md)).

| Condición | Momento | `error_code` sugerido |
|-----------|---------|------------------------|
| `code` fuera del subset Clean | Guardar / publicar | `file_clean_rule_unknown` |
| Regla de campo sin `field_name` o campo inexistente | Guardar / publicar | `file_clean_rule_field_missing` |
| `replace_map` sin `map` objeto no vacío | Guardar / publicar | `file_clean_replace_map_invalid` |
| `replace` con `find` ausente o `""` | Guardar / publicar | `file_clean_replace_find_required` |
| `compose` sin `template`, token no MVP, o `{field:X}` inválido | Guardar / publicar | `file_clean_compose_invalid` |
| `regex: true` en `replace` (MVP Clean) | Guardar / publicar | `file_clean_replace_regex_unsupported` |

Textos de usuario: catálogo [`UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) cuando se implemente.

---

## UI

- Lista ordenable (drag o subir/bajar).  
- Alta desde catálogo permitido (no free-text de código).  
- Editors: mapa clave-valor (`replace_map`); `find`/`replace` (`replace`); plantilla + ayuda de tokens (`compose`).  
- Preview de efecto en M5 (run), no aquí.

---

## Frontera con FilePipe

| Clean | Pipe |
|-------|------|
| Reglas de normalización pre-calidad | Reglas + mapeo hacia destino de negocio |
| Salida ≈ mismo esquema de lectura | Salida = TargetProfile |
| `compose` acotado (tokens fijos) | `concat` / `generated` / expresiones de mapeo |

Compartir librería de operadores; **no** copiar pantallas de mapeo N:1 / calculados al MVP Clean.

---

## API-ready

Las reglas viven en la versión publicada. API no acepta “rules inline” en MVP de plataforma.

---

## Criterio de aceptación

- [x] CRUD de reglas en borrador  
- [x] Orden persistente  
- [x] Rechazo de `code` desconocido  
- [x] Documentado el subset vs catálogo DMS completo  
- [x] `replace_map`: solo match exacto del valor completo  
- [x] `replace`: find/replace dentro del string; `find` vacío rechazado  
- [x] `compose`: tokens MVP `{value}`, `{field:name}`, `{seq}` + literales; secuencia por job  
- [x] Validaciones de params al guardar (P5 al publicar = M4)
