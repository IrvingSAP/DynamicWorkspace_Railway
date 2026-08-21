# Módulo 6 — Historial (FILE SPLIT / MERGE)

Listado y detalle de corridas `SplitMergeJob`: quién, cuándo, operación, hashes, versión, estado, descargas (TTL).

> **Estado:** implementado (M6)  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md)  
> **Dependencia:** M5 Ejecutar (`sm_run.md`)  
> **Rama:** fusionada a `main` (PR #13)  
> **Patrón hermano:** [`../definition_app_FILE_CLEAN/clean_history.md`](../definition_app_FILE_CLEAN/clean_history.md)

---

## Objetivo

Auditar jobs Split/Merge del proyecto con filtros, detalle (manifiesto de partes) y borrado solo de corridas propias.

---

## Pantallas y URLs

Prefijo: `/app/file-split-merge/proyectos/<slug>/historial/`

| Pantalla | Nombre |
|----------|--------|
| Hub | `history_hub` |
| Ayuda hub | `history_hub_help` |
| Detalle | `history_detail` |
| Eliminar propia | `history_delete_job` |
| Eliminar todas mías | `history_delete_own` |

Filtros: estado, operación (`split`/`merge`), TTL, fechas, usuario, archivo, hash, versión, preview/ejecución. Paginación 25.

---

## Roles

| Acción | PA/ED/GE | CO |
|--------|----------|-----|
| Ver listado / metadatos | ✓ | ✓ |
| Descargar artifacts | ✓ (TTL vigente) | — |
| Eliminar corridas propias | ✓ (ejecutor) | — |

---

## Criterios

1. Detalle Split muestra partes + conteos; Merge muestra filas / dedupe.  
2. Badge TTL / mensaje si expiró evidencia.  
3. No borrar jobs ajenos.  
4. Descargas vía `run_download` (M5).

---

## Implementación

| Pieza | Ruta |
|-------|------|
| Servicio | `apps/file_split_merge/history/services/sm_history_service.py` |
| Vistas | `apps/file_split_merge/history/views.py` |
| UI | `templates/file_split_merge/history/` |
| TTL | `sm_run_service.ARTIFACT_TTL` |
