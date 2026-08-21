# Módulo 5 — Ejecución / Job (FILE SPLIT / MERGE)

Definición e implementación de **upload → preview → job → artifacts** (Split 1→N o Merge N→1).

> **Estado:** implementado (M5)  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md)  
> **Integración:** [`sm_integration.md`](sm_integration.md)  
> **Dependencia:** M4 publicado (`sm_publish.md`)  
> **Rama:** `feature/file-split-merge`  
> **Patrón hermano:** [`../definition_app_FILE_CLEAN/clean_run.md`](../definition_app_FILE_CLEAN/clean_run.md)

---

## Objetivo

Subir archivo(s), previsualizar el efecto de las reglas publicadas y ejecutar un job que entrega artifacts.

```text
Resolver versión publicada (SM1)
  → Intake (límites, extensión, hash)
  → Parse soft según perfil (sin content_type Gate)
  → Motor Split o Merge (reglas ON de la versión)
  → Serializar salida(s) mismo file_type
  → Persistir SplitMergeJob + artifacts
  → Métricas + descargas (TTL)
```

---

## Flujos

### Split (1 archivo)

```text
Upload 1 → parse → partición (max_rows | max_bytes | split_by_column)
→ N partes + manifiesto → ZIP (run) / métricas (preview)
```

### Merge (≥2 archivos)

```text
Upload N (≥2) → parse cada uno → missing_columns → append → dedupe?
→ 1 salida merged
```

---

## Reglas de producto (SM*)

| ID | Regla |
|----|--------|
| SM1 | Solo versión **publicada activa**. |
| SM3 | Split: exactamente **1** entrada; ≥1 parte (0 filas → failed). |
| SM4 | Merge: **≥2** entradas; 1 salida. |
| SM5 | Fallo de parseo → `failed` sin output engañoso. |
| SM6 | Partes Split comparten layout del perfil. |
| SM7 | Merge: columnas según `missing_columns` (`error` \| `fill_empty`). |

Límite de seguridad Split: **máx. 200 partes** → `file_sm_split_limit`.

---

## Artifacts

| Operación | Salidas |
|-----------|---------|
| Split | `part_001…`, `manifest.json`, `parts.zip` |
| Merge | `merged.<ext>` (+ métricas dedupe) |

Storage: `storage_service` job input/output/reports + TTL 7 días (como Clean).

---

## Runner (API-ready)

```text
run_sm_job(user, project, files, *, dry_run=False, idempotency_key=None, version=None)
  → OperationResult { job_id, status, metrics, artifact_refs }
```

Sin `request` en el dominio. Preview = `dry_run=True` (sin ZIP/merged definitivo).

---

## Pantallas

Prefijo: `/app/file-split-merge/proyectos/<slug>/ejecutar/`

| Pantalla | Nombre |
|----------|--------|
| Hub | `run_hub` |
| Preview / Ejecutar POST | `run_preview` / `run_execute` |
| Resultado | `run_result` |
| Descargar | `run_download` (`zip`, `merged`, `manifest`, `input`, `part_…`) |

---

## Criterio de aceptación

- [x] Solo versión publicada  
- [x] Preview + run completo  
- [x] Split ZIP + manifiesto; Merge archivo único  
- [x] Runner invocable sin HTML  
- [x] Mensajes UI_MESSAGES §3.15 M5  
