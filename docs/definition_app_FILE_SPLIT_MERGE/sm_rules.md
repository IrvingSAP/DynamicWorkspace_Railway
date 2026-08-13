# Módulo 3 — Reglas Split / Merge (FILE SPLIT / MERGE)

Definición de la **operación** (`split` \| `merge`) y el **catálogo ordenado de reglas** que, junto al perfil de lectura (M2), forman el borrador publicable.

> **Estado:** implementado (M3)  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md) §7–§8  
> **Integración:** [`sm_integration.md`](sm_integration.md)  
> **Dependencia:** M2 implementado (`sm_profile.md`) — hub exige `profile_complete`  
> **Rama:** fusionada a `main` (PR #13)  
> **Patrón hermano:** [`../definition_app_FILE_CLEAN/clean_rules.md`](../definition_app_FILE_CLEAN/clean_rules.md)

---

## Objetivo

Permitir al PA/ED declarar **cómo se parte o se une** el archivo ya parseado según el perfil:

```text
Perfil completo (M2)
  → Elegir operación Split | Merge
  → Configurar reglas del catálogo (orden + params)
  → Guardar en borrador
  → (M4) Publicar congela perfil + operation + rules
```

Copy: **partición / consolidación**. No “transformar”, “limpiar” ni “conciliar”.

---

## Qué no es

| No | Motivo |
|----|--------|
| Perfil de lectura / campos | M2 |
| Publicar | M4 |
| Upload / job / ZIP | M5 |
| Limpieza de celdas | File Clean |
| Mapeo a destino | FilePipe |
| Conciliación | File Match |

---

## Alcance MVP

| Incluye | Excluye (Fase 2) |
|---------|------------------|
| Una operación por borrador: `split` **o** `merge` | Dos operaciones activas en la misma versión |
| Catálogo Split: `max_rows`, `max_bytes`, `split_by_column`, `keep_header` | `date_range`, `round_robin`, max partes |
| Catálogo Merge: `append`, `missing_columns`, `dedupe_rows`, `include_header` | Join por clave, sort global, Merge→Worksheet |
| Orden + enable/disable por regla | Diff inteligente al cambiar operación |
| Validación contra campos del perfil | Ejecución real (M5) |

---

## Integración técnica (objetivo)

| Pieza | Uso |
|-------|-----|
| `DmsSourceProfile.config` | Clave `sm_rules` (sin migración; como `clean_rules`) |
| `split_merge_rules_persistence_service` | Leer/guardar/validar borrador |
| `split_merge_rules_catalog` | Códigos, params schema, labels |
| Templates | `templates/file_split_merge/rules/` |
| Hub M1 | CTA Reglas activo si `profile_complete`; `rules_complete` según validación |

Estructura sugerida en `config.sm_rules`:

```json
{
  "operation": "split",
  "rules": [
    {
      "id": "uuid-or-local",
      "code": "max_rows",
      "enabled": true,
      "sort_order": 10,
      "params": { "n": 50000 }
    }
  ]
}
```

`operation` vacío o ausente → reglas incompletas (no se puede publicar).

---

## Pantallas y URLs

Prefijo: `/app/file-split-merge/proyectos/<slug>/reglas/`

| Pantalla | URL | Nombre |
|----------|-----|--------|
| Hub reglas | `` | `rules_hub` |
| Ayuda hub | `ayuda/` | `rules_hub_help` |
| Guardar operación (POST) | `operacion/` | `rules_set_operation` |
| Agregar regla | `nueva/` | `rules_add` |
| Editar regla | `<rule_id>/editar/` | `rules_edit` |
| Guardar regla (POST) | `<rule_id>/guardar/` o `nueva/guardar/` | `rules_save` |
| Toggle enable (POST) | `<rule_id>/toggle/` | `rules_toggle` |
| Reordenar (POST) | `reordenar/` | `rules_reorder` |
| Eliminar (POST) | `<rule_id>/eliminar/` | `rules_delete` |
| Ayuda por código (opcional) | `ayuda/<code>/` | `rules_code_help` |

Incluir en `apps/file_split_merge/urls.py` como Clean.

---

## Flujo UX

### 1. Entrada desde hub M1

- Si `not profile_complete` → CTA Reglas deshabilitado (como hoy).  
- Si perfil completo → enlace a `rules_hub` (`btn-primary` si incompleto, `btn-info` si `rules_complete`).

### 2. Hub reglas

| Zona | Contenido |
|------|-----------|
| Strip | Proyecto · rol · borrador · operación actual |
| Selector operación | Radio/cards: **Partir (Split)** \| **Unir (Merge)** |
| Alerta si cambia operación | “Se quitarán reglas incompatibles con la otra operación. ¿Continuar?” |
| Lista de reglas | Tabla: orden, código, resumen params, ON/OFF, acciones |
| Vacío | CTA “Agregar regla” + hint según operación |
| Footer | ← Proyecto · Continuar a Publicar (deshabilitado hasta M4 o hasta `rules_complete`) |

### 3. Alta / edición de regla

1. Elegir `code` del catálogo filtrado por `operation`.  
2. Formulario de params (HTML plano).  
3. Guardar → vuelve al hub con mensaje success.

`field_name` / `keys[]`: select con nombres internos del perfil (M2), no texto libre si hay campos.

---

## Catálogo Split (MVP)

| Código | Params | Default | Notas |
|--------|--------|---------|-------|
| `max_rows` | `n` (int ≥ 1) | — | Filas de **datos** por parte (post-captura) |
| `max_bytes` | `bytes` (int ≥ 1) | — | Corte aproximado; siempre en límite de fila |
| `split_by_column` | `field_name` (requerido), `include_empty` (bool) | `include_empty: false` | Una parte por valor distinto |
| `keep_header` | `enabled` implícito vía regla; `value` bool | `true` | Repetir encabezado en cada parte (delimited/xlsx). Si no hay regla, default **true** en run |

### Completitud Split (`rules_complete`)

Al menos **una** regla de partición **enabled** entre:

- `max_rows` · `max_bytes` · `split_by_column`

`keep_header` sola **no** basta.

Si hay varias de partición enabled: **permitido** en MVP (p. ej. `split_by_column` + `max_rows` como tope por parte) — documentar en ayuda; el runner M5 aplicará en orden `sort_order`.

---

## Catálogo Merge (MVP)

| Código | Params | Default | Notas |
|--------|--------|---------|-------|
| `append` | (sin params) | — | Concatenar en orden de upload. Puede ser implícito si no hay otras; si se lista, marca intención explícita |
| `missing_columns` | `mode`: `error` \| `fill_empty` | `error` | Si falta columna del perfil en algún archivo |
| `dedupe_rows` | `keys[]` (≥1 nombre de campo), `keep`: `first` \| `last` | `keep: first` | Opcional |
| `include_header` | `value` bool | `true` | Una fila de encabezado en la salida |

### Completitud Merge (`rules_complete`)

1. `operation === "merge"`.  
2. Política de columnas definida: existe regla `missing_columns` enabled **o** se aplica default `error` al guardar operación (recomendación UX: **crear automáticamente** `missing_columns` con `error` al elegir Merge la primera vez).  
3. No se exige `append` explícito (el merge siempre concatena; `append` es documentacional / opcional en lista).

`dedupe_rows` opcional. `include_header` default true si ausente.

---

## Cambio Split ↔ Merge

| Decisión | Contrato |
|----------|----------|
| Confirmación | Modal/POST con aviso |
| Efecto | Borrar todas las reglas del borrador **o** deshabilitar y filtrar solo incompatibles |
| MVP | **Limpiar reglas** al confirmar cambio de operación (simple, auditable) |
| `operation` | Actualizar en `sm_rules` en el mismo POST |

---

## Validaciones al guardar

| Caso | `error_code` / canal | Mensaje (borrador §3.15) |
|------|----------------------|---------------------------|
| Sin permiso | `forbidden` | No tiene permiso para editar las reglas de este proyecto. |
| Perfil incompleto | `validation_form` | Complete el perfil de lectura antes de definir reglas. |
| Código desconocido | `validation_form` | Regla no permitida en el catálogo. |
| Params inválidos | inline + `validation_form` | Revise los parámetros de la regla. |
| `split_by_column` sin campo / campo inexistente | inline | Seleccione un campo del perfil de lectura. |
| `dedupe_rows` keys vacías o inexistentes | inline | Indique al menos una clave de deduplicación válida. |
| `max_rows.n` &lt; 1 | inline | Indique un número de filas mayor o igual a 1. |
| Guardado OK | `success` | Reglas Split/Merge guardadas correctamente. |
| Operación actualizada | `success` | Operación actualizada. Revise el catálogo de reglas. |
| Cambio operación + limpia | `warning`/`success` | Operación cambiada. Se eliminaron las reglas anteriores. |

---

## Relación con perfil (M2)

| Regla | Dependencia |
|-------|-------------|
| `split_by_column` | `field_name` ∈ nombres del perfil |
| `dedupe_rows.keys` | Cada key ∈ nombres del perfil |
| Resto | No exigen campo concreto |

Si el usuario **renombra o borra** un campo referenciado (M2):

- Al guardar perfil: aviso (cuando exista M3) — “Reglas referencian campos eliminados”.  
- Al publicar (M4): bloquear si referencias rotas.  
- MVP M3: al editar/guardar regla, validar contra perfil actual; listado muestra badge “campo faltante” si aplica.

---

## Roles

| Acción | PA | ED | CO | GE |
|--------|----|----|----|-----|
| Ver hub / lista | ✓ | ✓ | ✓ | ✓ |
| Cambiar operación / CRUD reglas | ✓ | ✓ | — | — |
| Publicar | — (M4) | — | — | — |

---

## Hub M1 — cambios al implementar M3

| Antes | Después |
|-------|---------|
| CTA Reglas `aria-disabled` | Enlace si `profile_complete` |
| `rules_complete` False | Calculado por validación Split/Merge |
| `operation_label` «—» | `Split` / `Merge` / «Sin operación» |
| `draft_label` | Incluye operación + N reglas ON |

---

## Ayudas (contenido mínimo)

| Pantalla | Explicar |
|----------|----------|
| Hub | Split = 1→N; Merge = N→1; una operación por versión |
| Cambio operación | Se pierden reglas del modo anterior |
| `max_rows` / `max_bytes` | Sobre filas ya capturadas; no confundir con tamaño de archivo crudo sin parsear |
| `split_by_column` | Nombre interno del perfil; valores vacíos según `include_empty` |
| `missing_columns` | `error` falla el job; `fill_empty` rellena |
| `dedupe_rows` | Tras concatenar; no es Match |

---

## Prototipos (tras OK de esta spec)

| Archivo | Destino futuro |
|---------|----------------|
| `prototype/file_split_merge/rules_hub.html` | `templates/file_split_merge/rules/hub.html` |
| `rules_hub_help.html` | ayuda |
| `rules_add_split.html` / `rules_edit_*.html` | formularios por código o genérico |
| `rules_add_merge.html` | idem Merge |

Escenario demo: perfil CSV con campos `sucursal`, `documento`, `monto` · operación Split · `split_by_column` + `keep_header`.

---

## Criterio de aceptación del módulo

- [x] Spec completa revisada (este doc)  
- [x] Prototipos reglas + ayudas (`prototype/file_split_merge/rules_*.html`)  
- [x] Revisión UX OK  
- [x] «Desarrolla el módulo» → `apps/file_split_merge/rules/` + templates + hub M1  
- [x] Persistencia `config.sm_rules` sin migración  
- [x] `rules_complete` Split/Merge según tablas de este doc  
- [x] Mensajes §3.15 M3  
- [x] Cambio operación limpia reglas (MVP)  

---

## Prototipos creados

Abrir: [`../../prototype/file_split_merge/index.html`](../../prototype/file_split_merge/index.html)

| Archivo | Pantalla |
|---------|----------|
| `rules_hub.html` | Hub Split + lista |
| `rules_hub_merge.html` | Variante Merge |
| `rules_hub_help.html` | Ayuda |
| `rules_change_operation.html` | Confirmación limpia reglas |
| `rules_add_split.html` | Alta/edición Split |
| `rules_add_merge.html` | Alta/edición Merge |

> `prototype/` en `.gitignore`. Código: `templates/file_split_merge/rules/`.

---

*Siguiente: M4 Publicar (`sm_publish.md`) — definir → prototipar → «Desarrolla el módulo».*
