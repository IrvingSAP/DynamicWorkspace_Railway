# Fase 2 — Longitudes estimadas editables (STRUCTURE SCOUT)

Proceso y especificación de **mejora de definición de campos** en el Explorador: proponer y permitir editar **`start` / `end` / `length`** (y, si aplica, marcador `char`) ya en Scout — sobre todo para `txt_fixed` — antes de guardar el borrador y aplicar a destino.

> Estado: **especificación (documentación)**. Sin implementación de código hasta OK explícito («Desarrolla…»).  
> Producto: [`../STRUCTURE_SCOUT.md`](../STRUCTURE_SCOUT.md) §7.3 / S7.  
> Rama: `feature/scout-mejoras-campos`.  
> Extiende: [`propose_fields.md`](propose_fields.md) (M4), [`save_draft.md`](save_draft.md) (M5), [`apply_target.md`](apply_target.md) (M6), [`detect_pattern.md`](detect_pattern.md) (M3).  
> Base técnica: `resolve_txt_fixed_bounds` / `normalize_fields_list` (`apps.dms.source_profile`), muestra M2 + patrón M3.  
> App objetivo (cuando se implemente): `apps/structure_scout/fields/` · Templates: `templates/structure_scout/fields/`.

---

## Propósito

Cerrar el hueco del MVP: Scout **estima estructura** pero, en posicional, **no** ofrecía longitudes editables; el apply sembraba placeholders `1..N` no solapados y el usuario afinaba solo en GATE/Reverse.

En Fase 2, Scout debe:

1. **Proponer** rangos/longitudes estimadas a partir de la muestra (heurística; sin LLM obligatorio);
2. Dejarlas **editables** en la tabla de Campos (M4);
3. Congelarlas en `StructureDraft` (`source.fields` + meta en `draft.fields`);
4. Al aplicar (M6), **mapear** esos valores al destino (ya no inventar placeholders ciegos).

Scout sigue **proponiendo**; no publica el destino (S2 / SS3).

```
Muestra + patrón txt_fixed (M3)
        →
Heurística de anchos / cortes (Fase 2)
        →
Tabla Campos: name, tipo, required, start/end/length [editables]
        →
Confirmar → ScoutFieldsState
        →
M5 StructureDraft (source.fields con bounds)
        →
M6 apply → save_source con bounds reales del draft
```

---

## Qué es / qué hace / qué no hace

| Pregunta | Respuesta |
|----------|-----------|
| **¿Qué es?** | Extensión de M4 (y contrato de payload M5/M6) para **definición posicional estimada** |
| **¿Qué hace?** | Propone y edita `start`/`end`/`length` (opcional `char`); valida no solape; persiste en estado y draft |
| **¿Qué no hace?** | No convierte Scout en editor completo de captura GATE. No publica. No exige longitudes “perfectas” de producción. No LLM obligatorio |
| **Copy UX** | “Longitud / posición estimada” / “afinar rangos” — no “contrato publicado” ni “validar archivo de producción” |

---

## Motivación (por qué ahora)

| MVP (hoy) | Problema | Fase 2 |
|-----------|----------|--------|
| M4 sin columnas de longitud | Usuario no puede expresar posicional en Scout | Columnas editables cuando `file_type_code = txt_fixed` |
| Apply: placeholders `i+1` de longitud 1 | Destino recibe rangos artificiales | Apply usa bounds del draft |
| S7: revisión manual de longitudes | La revisión ocurría **solo** en el destino | Revisión **también** en Scout; destino sigue siendo lugar de publicación |
| Heurística posicional débil | `needs_review` permanente | Heurística mejorada + confianza por campo de longitud |

---

## Alcance

| Incluido | Excluido (sigue fuera / otra Fase) |
|----------|-------------------------------------|
| UI + persistencia `start`/`end`/`length` en M4 si `txt_fixed` | Captura inicio/fin avanzada (`capture_start`/`capture_end`) — sigue Fase 2 detect / GATE |
| Heurística de estimación de anchos (documentada abajo) | LLM para inferir cortes |
| Validación no solape / end ≥ start / length ≥ 1 (alineada a `validate_source_dict`) | Diff campo-a-campo al apply (otra ítem §7.3) |
| Payload M5 `source.fields[]` con bounds | JSON/XML |
| M6: mapear bounds del draft (sin placeholders ciegos si hay datos) | Auto-publicar destino |
| Ayuda / mensajes UI | Match B / FilePipe |

### Cuándo se muestran las columnas

| `file_type_code` (M3) | Columnas start/end/length |
|-----------------------|---------------------------|
| `txt_fixed` | **Sí** (obligatorio editar o aceptar estimación) |
| `csv` / `txt_delimited` / `xlsx` | **No** (siguen `column_index` / `column` como hoy) |

---

## Heurística de estimación (MVP Fase 2 — sin LLM)

Objetivo: propuesta **usable**, no óptima. Siempre `needs_review` o confianza `medium`/`low` en bounds hasta que el usuario confirme.

### Entradas

- Filas de preview de la muestra (M2) alineadas al patrón M3.
- Opcional: delimitador “débil” o espacios múltiples si la muestra parece columnar por blancos.

### Estrategias (en orden de preferencia)

| # | Estrategia | Cuándo | Resultado |
|---|------------|--------|-----------|
| H1 | Cortes por **runs de 2+ espacios** / columnas visuales en N filas | Muestra alineada tipo “report” | `start`/`end` por columna detectada |
| H2 | Ancho = **max longitud** de celda observada por columna tentativa | Ya hay N campos de M4 (nombres) pero sin bounds | `length = max(1, max_len)`; `start` acumulado |
| H3 | Fallback **placeholders secuenciales** longitud 1 (`1-1`, `2-2`, …) | Heurística falla / &lt;3 filas | Igual que apply MVP actual + `needs_review` + nota |

### Reglas de confianza de bounds

| Condición | `length_confidence` (meta) | Efecto |
|-----------|----------------------------|--------|
| H1 estable en ≥3 filas, mismos cortes | `medium` | Puede confirmar; status global puede seguir `needs_review` si M3 era posicional |
| H2 solo max-len | `low` | Forzar hint “estime / revise longitudes” |
| H3 fallback | `low` | `needs_review` obligatorio |

**Nota:** la confianza de **tipo** (`content_type`) y la de **longitud** son independientes; el peor caso empuja status global.

---

## Forma de campo (extensión)

### Persistencia `ScoutFieldsState.fields[]` (M4)

Además de M4 actual (`name`, `content_type`, `required`, `confidence`, `examples`, `notes`):

| Campo | Editable | Notas |
|-------|----------|-------|
| `start` | Sí (si `txt_fixed`) | 1-based, inclusive |
| `end` | Sí | ≥ `start`; o se deriva de `start`+`length` |
| `length` | Sí | ≥ 1; si se edita, recalcular `end` |
| `char` | Opcional Fase 2.1 | Marcador; fuera del primer corte si complica UX |
| `length_confidence` | No directo | `high`/`medium`/`low` (meta Scout) |
| `length_notes` | Opcional | p. ej. `heuristic_spaces`, `fallback_unit` |

UI: al cambiar `start` o `length`, actualizar `end` (y viceversa) con la misma lógica que `resolve_txt_fixed_bounds`.

### Bloque `source.fields[]` (M5 / apply)

Alineado a SourceProfile / `normalize_fields_list`:

```json
{
  "name": "documento",
  "label": "documento",
  "content_type": "numeric",
  "required": true,
  "start": 1,
  "end": 12,
  "length": 12
}
```

Meta Scout (`confidence`, `examples`, `length_confidence`, …) permanece en `draft.fields`; `source.fields` limpio para el destino.

### M6 `map_scout_source_to_partials`

| Situación | Comportamiento |
|-----------|----------------|
| Campo con `start`/`end`/`length` válidos | Copiar al partial (sin placeholder) |
| Campo `txt_fixed` sin bounds | Fallback H3 (secuencial) + warning en apply |
| Tipo no posicional | Sin cambios vs MVP |

---

## UI (M4 hub)

| Elemento | Comportamiento |
|----------|----------------|
| Columnas `Inicio` / `Fin` / `Long.` | Visibles solo si detección es `txt_fixed` |
| Inputs numéricos | Validación cliente suave + servidor al confirmar |
| Badge / hint | “Estimado — revise antes de aplicar” si `length_confidence` ≠ high |
| Ayuda «¿Qué significa?» | Extender diálogo needs_review / ayuda campos: explicar estimación vs contrato destino |
| Re-inferir | Recalcula tipos **y** bounds (warning: pierde overrides de longitud) |

No usar Django Forms; HTML plano + JS de reindex (como hoy).

---

## Flujo de usuario

1. Usuario en Campos con patrón `txt_fixed` confirmado.
2. Sistema muestra tabla con bounds estimados (H1→H2→H3).
3. Usuario ajusta longitudes / posiciones.
4. Confirma → `ScoutFieldsState` con bounds; status respeta S7 si bounds `low`.
5. Guarda borrador (M5) → `source.fields` lleva bounds.
6. Aplica (M6) → destino recibe los mismos bounds; usuario publica en GATE/Reverse.

---

## Reglas de negocio

| ID | Regla |
|----|-------|
| FL1 | Bounds editables en Scout **solo** para `txt_fixed` en esta Fase. |
| FL2 | Confirmar campos valida no solape y `end ≥ start` / `length ≥ 1` (misma semántica que `validate_source_dict` no-strict + errores de rango). |
| FL3 | Estimación nunca auto-publica ni escribe SourceProfile ajeno hasta M6. |
| FL4 | Si el usuario no toca bounds y H3 aplicó, status mínimo `needs_review`. |
| FL5 | M6 no debe pisar bounds válidos del draft con placeholders. |
| FL6 | CO: sin ejemplos; puede ver metadatos de longitud si la matriz actual lo permite (sin datos de muestra). |
| FL7 | PA/ED editan bounds; GE: misma política que M4 MVP (ver/aceptar según matriz vigente). |
| FL8 | Sin Django Forms; mensajes vía `UI_MESSAGES` (añadir filas al implementar). |
| FL9 | Reuso DMS: no duplicar `resolve_txt_fixed_bounds`; Scout solo propone y persiste. |

---

## Validaciones (al confirmar M4 / al armar source M5)

| Situación | Severidad | Texto orientativo |
|-----------|-----------|-------------------|
| Falta start/end/length en `txt_fixed` | Error | Indique inicio/fin o longitud de cada campo posicional. |
| `end` &lt; `start` | Error | El fin debe ser ≥ al inicio. |
| `length` &lt; 1 | Error | La longitud debe ser ≥ 1. |
| Solape de rangos | Error | Hay campos posicionales que se solapan; ajuste inicio/fin. |
| Solo estimación H3 | Warning | Longitudes provisionales (1 columna). Revise antes de aplicar. |
| Cobertura &lt; 3 filas | Warning | Muestra corta: la estimación de anchos es débil. |

(Textos finales al implementar → catálogo [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) § STRUCTURE SCOUT.)

---

## Impacto por módulo

| Módulo | Cambio documental / futuro código |
|--------|-----------------------------------|
| M3 Detectar | Sin UI de longitudes; puede anotar hint “longitudes en Campos (Fase 2)” |
| **M4 Campos** | **Principal:** columnas + heurística + validación |
| M5 Borrador | `build_payload` incluye bounds en `source.fields` |
| M6 Aplicar | `map_scout_source_to_partials` respeta bounds |
| M7 Historial | Detalle puede mostrar N campos + “con longitudes” (opcional) |
| Ayudas / guía | Actualizar copy: Scout puede estimar longitudes; destino publica |

---

## Criterios de aceptación (para cuando se implemente)

| # | Criterio |
|---|----------|
| A1 | Con muestra `txt_fixed`, M4 muestra start/end/length editables. |
| A2 | Heurística propone valores; usuario puede corregir y confirmar. |
| A3 | Solapes bloquean confirmación con mensaje claro. |
| A4 | Draft export/JSON incluye bounds en `source.fields`. |
| A5 | Apply a GATE/Reverse no usa placeholders si el draft trae bounds válidos. |
| A6 | CSV/delimitado/xlsx **no** muestran columnas de longitud. |
| A7 | Sin regresión: flujo no posicional igual que MVP. |
| A8 | Documentación de ayuda actualizada; sin auto-publish. |

---

## Fuera de este documento / siguientes cortes

| Tema | Dónde |
|------|-------|
| Heurística posicional “robusta” end-to-end en M3 | [`detect_pattern.md`](detect_pattern.md) / STRUCTURE_SCOUT §7.3 |
| `char` / marcadores en UI Scout | Fase 2.1 de este mismo hilo |
| Captura % / markers en Scout | Fase 2 detect / destino |
| LLM nombres / máscaras | STRUCTURE_SCOUT §7.3 |

---

## Decisiones abiertas (para revisión antes de código)

| # | Pregunta | Propuesta por defecto |
|---|----------|------------------------|
| D1 | ¿Editar solo `length` + `start`, o también `end` libre? | Los tres, con sincronización `resolve_txt_fixed_bounds` |
| D2 | ¿Re-inferir pisa longitudes siempre? | Sí, con confirmación/warning (como tipos hoy) |
| D3 | ¿Bounds en delimitado alguna vez? | No en esta Fase |
| D4 | ¿Prototipo HTML obligatorio antes de código? | **Sí** (método definition_app): `prototype/structure_scout/fields/` |

---

## Próximos pasos (ritual)

1. Revisar este doc (chat / OK del usuario).  
2. Prototipo HTML de la tabla con columnas de longitud.  
3. Usuario: **«Desarrolla…»** → implementación en `feature/scout-mejoras-campos`.  
4. Actualizar `UI_MESSAGES.md` + ayudas en el mismo PR de código.

---

## Referencias

| Doc | Relación |
|-----|----------|
| [`../STRUCTURE_SCOUT.md`](../STRUCTURE_SCOUT.md) | S7, §7.3 Fase 2 |
| [`propose_fields.md`](propose_fields.md) | M4 base |
| [`save_draft.md`](save_draft.md) | Payload `source` |
| [`apply_target.md`](apply_target.md) | Mapeo apply |
| [`detect_pattern.md`](detect_pattern.md) | `txt_fixed` / needs_review |
| [`README.md`](README.md) | Índice definition_app Scout |
