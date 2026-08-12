# FILE SPLIT / MERGE — Integración transversal

> **Archivo:** `sm_integration.md`  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md)  
> **Estado:** borrador

---

## 1. Kind y chasis

| Ítem | Valor |
|------|--------|
| `Project.project_kind` | `file_split_merge` |
| Label UI | **File Split/Merge** (Title Case) |
| App Django (objetivo) | `apps/file_split_merge/` |
| Namespace URLs | `file_split_merge:` |
| Prefijo | `/app/file-split-merge/` |
| Estado M1 | **Implementado** (listado, alta, hub, miembros, guía, sidebar) |

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
| UI_MESSAGES / error_code | Respuestas servicio |

**No reusar:** Target mapping de negocio, Match compare, reglas de limpieza Clean (salvo dedupe genérico si se comparte motor).

---

## 4. Encadenamiento (MVP manual)

```text
Clean (opcional) → Split/Merge (descarga) → usuario sube a Gate / Pipe / Match
```

---

## 5. PLATFORM_API (futuro)

| Kind | Entrada | Salida |
|------|---------|--------|
| `file_split` | 1 file | N outputs + manifiesto |
| `file_merge` | `files[]` | 1 output |

Alternativa: un solo `kind=file_split_merge` + `operation` en el body. Decidir en implementación API; el runner interno debe soportar ambas operaciones.

---

## 6. Sidebar

Entrada en menú UF junto a File Clean / Gate / Match, solo si la compañía/paquete lo habilita (mismo patrón de feature flags si aplica).

---

*Actualizar este archivo al cablear settings, urls y migración de kind.*
