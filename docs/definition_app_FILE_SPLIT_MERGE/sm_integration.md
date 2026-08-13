# FILE SPLIT / MERGE — Integración transversal

> **Archivo:** `sm_integration.md`  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md)  
> **Estado:** **parcial** — chasis / kind / UI **vivos** en `main`; contrato HTTP **diferido** a [`PLATFORM_API.md`](../PLATFORM_API.md)

Este documento no bloquea el cierre del vertical M1–M6. La ampliación de §5 (kinds HTTP, auth, payloads) se hace **cuando se desarrolle la capa PLATFORM API**, no como módulo pendiente de la app Split/Merge.

---

## 1. Kind y chasis (implementado)

| Ítem | Valor |
|------|--------|
| `Project.project_kind` | `file_split_merge` |
| Label UI | **File Split/Merge** (Title Case) |
| App Django | `apps/file_split_merge/` |
| Namespace URLs | `file_split_merge:` |
| Prefijo | `/app/file-split-merge/` |
| Migración kind | `apps/projects/migrations/0008_add_file_split_merge_kind.py` |
| M1–M6 | **Implementados** (proyecto → historial) |

---

## 2. Roles

Mapa PA / ED / CO / GE — ver [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md) §10.  
Ejecución (GE) alineada a Clean/Gate para PLATFORM_API.

---

## 3. Reuso DMS / Clean

| Componente | Uso |
|------------|-----|
| Source file types / parsers | Perfil de lectura |
| Serializers | Escritura de partes / consolidado |
| Intake / storage jobs | Upload y artifacts |
| Patrones Clean (hub, publish, history) | UI y ciclo de vida |
| UI_MESSAGES / error_code | Respuestas servicio · §3.15 |

**No reusar:** Target mapping de negocio, Match compare, reglas de limpieza Clean (salvo dedupe genérico si se comparte motor).

---

## 4. Encadenamiento (MVP manual)

```text
Clean (opcional) → Split/Merge (descarga) → usuario sube a Gate / Pipe / Match
```

---

## 5. PLATFORM_API (diferido)

> Ampliar esta sección al implementar [`../PLATFORM_API.md`](../PLATFORM_API.md). El runner interno (`run_sm_job`) ya es el punto de enganche.

| Kind (propuesta) | Entrada | Salida |
|------------------|---------|--------|
| `file_split` | 1 file | N outputs + manifiesto |
| `file_merge` | `files[]` | 1 output |

Alternativa: un solo `kind=file_split_merge` + `operation` en el body. Decidir en implementación API; el runner interno soporta ambas operaciones.

---

## 6. Sidebar

Entrada en menú UF junto a File Clean / Gate / Match (`templates/includes/sidebar_uf.html`), sujeta a paquete/feature flags si aplica.

---

*Chasis cableado. Pendiente solo el contrato HTTP unificado con PLATFORM_API.*
