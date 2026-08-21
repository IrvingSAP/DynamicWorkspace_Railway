# Módulo 2 — Perfil de lectura (FILE SPLIT / MERGE)

Definición de **cómo se lee** el archivo en un proyecto File Split/Merge: tipo, encoding, captura y campos. El mismo perfil alimenta Split (1→N) y Merge (N→1).

> **Estado:** implementado (M2)  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md)  
> **Integración:** [`sm_integration.md`](sm_integration.md)  
> **Reuso:** [`../definition_app_DMS/source_definition.md`](../definition_app_DMS/source_definition.md) · patrón [`../definition_app_FILE_CLEAN/clean_profile.md`](../definition_app_FILE_CLEAN/clean_profile.md)  
> **Rama:** `feature/file-split-merge`  
> **Dependencia:** M1 implementado (`project_lifecycle.md`)

---

## Objetivo

Permitir al PA/ED definir un **perfil de lectura versionable (borrador)** para que, al ejecutar:

- **Split** separe filas ya parseadas en N partes;
- **Merge** concatene/homologue archivos del **mismo layout**.

Clean no inventa un segundo parser: **reutiliza** SourceProfile / wizard DMS (skin File Split/Merge), igual que File Clean.

```text
Elegir tipo de archivo
  → Inicio de captura
  → Fin de captura
  → Definir campos (según tipo)
  → Guardar en borrador
```

---

## Qué no es

| No | Motivo |
|----|--------|
| Reglas Split/Merge | M3 (`sm_rules.md`) |
| Publicar | M4 |
| Validación Gate / content_type estricto en job | Soft-parse en M5 (como Clean) |
| Mapeo a destino de negocio | FilePipe |
| Limpieza de celdas | File Clean |

---

## Alcance MVP

| Incluye | Excluye |
|---------|---------|
| Tipos soportados por parsers DMS activos (csv, txt_delimited, txt_fixed, xlsx, json, xml) | Diseñar layout destino |
| Wizard 4 pasos (tipo → captura inicio → captura fin → campos) | Detección automática Scout (Fase 2: importar desde muestra) |
| Encoding / BOM / delimitador / hoja / paths JSON-XML según tipo | Obligatoriedad tipo Gate |
| Campos con nombre interno + metadatos de posición/columna | Reglas de partición en este módulo |
| Guardado en borrador sin publicar | Ejecución de job |
| Import Seed desde Gate/Clean publicados | Orígenes Seed Fase 2 (Match, Reverse, FilePipe, SM→SM) |

---

## Integración técnica (objetivo)

| Pieza | Uso |
|-------|-----|
| `source_persistence_service` | Leer/guardar perfil en SourceProfile del proyecto |
| `source_profile_service` / wizard | Pasos 1–4 y variantes de paso 4 |
| `profile_wizard_service` (app SM) | Skin: URLs `file_split_merge:profile_*`, labels |
| Templates | Copiar/adaptar `templates/file_clean/profile/` → `templates/file_split_merge/profile/` |
| Hub M1 | Enlace «Definir perfil» activo cuando M2 exista; `profile_complete` cuando `steps_complete >= 4` y ≥1 campo |

**No fork** del motor de parseo. Solo namespace, copy y ayudas propias.

---

## Pantallas y URLs

| Pantalla | URL | Nombre |
|----------|-----|--------|
| Hub perfil | `/app/file-split-merge/proyectos/<slug>/perfil/` | `profile_hub` |
| Ayuda hub | `…/perfil/ayuda/` | `profile_hub_help` |
| Guardar (POST) | `…/perfil/guardar/` | `profile_save` |
| Paso 1 tipo | `…/perfil/paso/1/` | `profile_step1` |
| Paso 2 inicio captura | `…/perfil/paso/2/` | `profile_step2` |
| Paso 3 fin captura | `…/perfil/paso/3/` | `profile_step3` |
| Paso 4 campos | `…/perfil/paso/4/` | `profile_step4` (+ variantes delimited/xlsx/json/xml) |
| Ayudas por paso | `…/paso/<n>/ayuda/` | `profile_stepN_help` (+ helps por tipo en paso 4) |

Prefijo app: incluir en `apps/file_split_merge/urls.py` como Clean.

---

## Wizard — 4 pasos

| # | Título | Contenido |
|---|--------|-----------|
| 1 | Tipo de archivo | `file_type_code` (csv, txt_delimited, txt_fixed, xlsx, json, xml…) |
| 2 | Inicio de captura | `capture_start` (first, line, skip, marker, pattern…) |
| 3 | Fin de captura | `capture_end` (eof, line, max_rows, marker…) |
| 4 | Campos | Layout según tipo: posiciones, índices CSV, letras/encabezados Excel, json_path, element XML |

### Paso 4 — variantes (misma lógica que Clean)

| Tipo | Editor | Ayuda |
|------|--------|-------|
| `txt_fixed` | Rangos / longitud / char | `step4_help_fixed` |
| `csv` / `txt_delimited` | Delimitador + índice 0-based + regex custom | `step4_help_delimited` |
| `xlsx` | Hoja + columna (letra o encabezado) | `step4_help_xlsx` |
| `json` | `record_path` + `json_path` | `step4_help_json` |
| `xml` | `record_element` + `element` | `step4_help_xml` |

Defaults CSV: delimitador **coma** (como fix Clean). TXT delimitado: `;` por defecto.

### Campos mínimos por ítem

| Atributo | Notas |
|----------|-------|
| `name` | Slug interno único (lo usará M3: `split_by_column.field_name`, dedupe keys) |
| `label` | Opcional |
| `content_type` | Documentación; **no** rechaza filas en Split/Merge run |
| `required` | Marca de perfil; no bloquea soft-parse |
| `pattern` | Si `custom`; se guarda; soft-parse no falla por mismatch |
| Posición / columna / path | Según tipo |

---

## Completitud (habilita M3 / M4)

El perfil se considera **completo** cuando:

1. Hay `file_type_code` válido.  
2. Hay `capture_start` y `capture_end` con `mode`.  
3. Hay **≥ 1 campo** con `name` válido.  

Hasta entonces:

- Hub M1: CTA Perfil = `btn-primary`; Reglas/Publicar bloqueados o avisados.  
- `profile_complete = False` en `get_hub_context`.

---

## Relación con reglas (M3)

| Regla M3 | Dependencia del perfil |
|----------|------------------------|
| `split_by_column` | `field_name` debe existir en el perfil |
| `dedupe_rows.keys` | Cada key = nombre de campo del perfil |
| `max_rows` / `max_bytes` / `append` | No exigen campo concreto |

Al **borrar o renombrar** un campo referenciado por reglas (cuando exista M3):

- Avisar al guardar perfil y/o bloquear publicar (mismo espíritu Clean P5).  
- MVP M2 solo: documentar el contrato; implementar aviso cuando M3 exista.

---

## Soft-parse (contrato para M5)

En ejecución Split/Merge (como Clean ≠ Gate):

- Adaptar campos a `free_text` / no required / sin pattern estricto al parsear.  
- 0 filas válidas → job `failed` con mensaje claro (captura / delimitador / layout).  
- Delimitador incorrecto → mensaje específico (patrón Clean).

---

## Roles

| Acción | PA | ED | CO | GE |
|--------|----|----|----|-----|
| Ver hub / pasos (lectura) | ✓ | ✓ | ✓ | ✓ |
| Editar / guardar borrador | ✓ | ✓ | — | — |
| Publicar | — (M4) | — | — | — |

CO/GE: solo lectura del perfil (sin POST guardar).

---

## Mensajes UI (M2) — borrador

Extender [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.15:

| Situación | Tag | Texto |
|-----------|-----|--------|
| Perfil guardado | `success` / JSON | Perfil de lectura guardado correctamente. |
| Validación perfil | `error` + inline / JSON | Revise los datos del perfil de lectura. |
| Sin permiso editar | `error` / 403 | No tiene permiso para editar el perfil de lectura de este proyecto. |
| JSON inválido | `error` | JSON de perfil inválido. |
| Tipo sin editor | `warning` | El tipo de archivo seleccionado aún no tiene editor de campos. Elija un tipo soportado en el paso 1. |

---

## Ayudas (contenido mínimo)

| Pantalla | Qué explicar |
|----------|----------------|
| Hub perfil | Perfil compartido Split/Merge; no elige operación aquí |
| Paso 1 | Tipos; CSV vs TXT delimitado |
| Paso 2–3 | Captura de filas (no confundir con fila de encabezado CSV) |
| Paso 4 por tipo | Índice 0-based, letra Excel vs encabezado, json_path, etc. |
| Regex custom | Solo si tipo `custom`; soft-parse no rechaza en run |

Copy: **lectura / layout**, no “limpieza” ni “conciliación”.

---

## Hub M1 — cambios al implementar M2

| Antes (M1 solo) | Después |
|-----------------|--------|
| CTA Perfil `aria-disabled` | Enlace a `profile_hub` / `continue_step_url_name` |
| `profile_complete` siempre False | Calculado por wizard |
| `draft_label` fijo «Sin perfil» | Tipo · N campos · versión borrador |

---

## Fuera de alcance M2

- Catálogo de reglas Split/Merge (M3).  
- Publicar / run / historial de jobs.  
- Importar desde Structure Scout (muestra → draft; distinto de Seed).  
- Orígenes Seed Fase 2: Match A/B, Reverse, FilePipe, SM→SM.  
- PLATFORM_API.

---

## Importar estructura (Profile Seed)

CTA **Importar estructura** (PA/ED) en el hub de perfil y en el **paso 4 (Campos)** — mismo flujo Profile Seed. Reusa `apps.profile_seed` + templates `templates/profile_seed/` (host Split/Merge vía `seed_host`).

| Fase | Orígenes → destino Split/Merge |
|------|--------------------------------|
| **Ahora** | **FILE GATE** (esquema publicado) · **FILE CLEAN** (perfil de lectura publicado) |
| **Fase 2** (compatibles, pendientes) | FILE MATCH (Perfil A/B) · Reverse Studio (entrada) · FilePipe/DMS (origen) · otro proyecto Split/Merge · Structure Scout apply |

Reglas: misma compañía, origen con versión **publicada**, escritura solo **borrador** (`save_source`), overwrite con aviso, auditoría `ProfileSeedEvent`, no auto-publicar.

URLs host: `/app/file-split-merge/proyectos/<slug>/perfil/importar/…`

Ver también [`../PROFILE_SEED.md`](../PROFILE_SEED.md).

---

## Prototipos (tras OK de esta spec)

| Archivo | Destino futuro |
|---------|----------------|
| `prototype/file_split_merge/profile_hub.html` | `templates/file_split_merge/profile/hub.html` |
| `profile_step1…4.html` (+ helps / variantes) | `templates/file_split_merge/profile/…` |

Reutilizar visualmente Clean profile; cambiar eyebrow, breadcrumb y textos Split/Merge.

---

## Criterio de aceptación del módulo

- [x] Spec completa revisada (este doc)  
- [x] Prototipos perfil + ayudas (`prototype/file_split_merge/profile_*.html`)  
- [x] Revisión UX OK  
- [x] «Desarrolla el módulo» → `apps/file_split_merge/profile/` + templates + cableado hub M1  
- [x] Reuso `source_persistence` / wizard DMS sin fork de parsers  
- [x] Completitud: tipo + captura + ≥1 campo  
- [x] Mensajes §3.15 M2  
- [x] Soft-parse documentado para M5  
- [x] Import Seed Gate/Clean → SM implementado; resto Fase 2 documentado  

---

## Prototipos creados

Abrir: [`../../prototype/file_split_merge/index.html`](../../prototype/file_split_merge/index.html)

| Archivo | Pantalla |
|---------|----------|
| `profile_hub.html` (+ `_help`) | Hub perfil |
| `profile_step1.html` (+ `_help`) | Tipo |
| `profile_step2.html` (+ `_help`) | Inicio captura |
| `profile_step3.html` (+ `_help`) | Fin captura |
| `profile_step4_delimited.html` (+ `_help`) | Campos CSV (variante principal) |

> `prototype/` en `.gitignore`. Código Django: `templates/file_split_merge/profile/` + import `templates/profile_seed/`.

---

*Siguiente: M3 Reglas (`sm_rules.md`) — definir → prototipar → «Desarrolla el módulo».*
