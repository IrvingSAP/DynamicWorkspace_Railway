# Módulo 5 — Ejecución / Job (FILE CLEAN)

> **App:** File Clean  
> **Estado:** implementado  
> **Crítico para API-ready:** el runner debe poder invocarse sin HTML

---

## Objetivo

Subir un archivo, aplicar la versión publicada, generar **archivo limpio** + **log de cambios**, con preview opcional.

---

## Flujo

```text
Resolver versión publicada
  → Intake (límites, extensión, hash)
  → Parsear según perfil
  → Aplicar reglas en orden (estado de secuencia por job si hay compose/{seq})
  → Serializar salida (mismo file_type / encoding destino de regla)
  → Persistir CleanJob + artifacts
  → Mostrar métricas + descargas
```

### Preview

- N primeras filas antes/después.  
- No persiste artifact definitivo (o marca `dry_run`).  
- GE/PA/ED según roles.  
- En preview, `{seq}` arranca en `seq_start` de la versión (mismo contrato que el job completo).

---

## Artifacts

| Artifact | Descripción |
|----------|-------------|
| `input` | Archivo original (TTL como samples/jobs DMS) |
| `output` | Archivo limpio descargable |
| `change_log` | JSON/CSV: fila, campo, regla (`code`), before, after — incluye `replace_map`, `replace`, `compose`, etc. |
| `metrics` | filas leídas, filas escritas, cambios, dedupe count, duración; opcional conteo por `code` |

---

## Aplicación de reglas en el runner

- Solo reglas **habilitadas** de la versión publicada, en `sort_order`.  
- Params ya validados en publish (P5); el runner **no** reescribe reglas desde la request.  
- **`{seq}` / `compose`:** un contador por job; reinicia en cada ejecución; orden = orden estable de filas del reader (ver [`clean_rules.md`](clean_rules.md)).  
- **`replace_map`:** sin match exacto → valor intacto (no error de job).  
- **`replace`:** aplica find/replace según params; sin coincidencias → intacto.

### Fallos en runtime

| Caso | Resultado |
|------|-----------|
| Parseo / I/O | Job `failed`; sin `output` engañoso (FC5) |
| Def. de regla corrupta (no debería tras P5) | Job `failed`; log técnico; `error_code` tipo `file_clean_rule_runtime` |
| Valor de dato “raro” sin match de mapa | Continuar; celda sin cambio |

Reglas que dejan fila vacía: política explícita (mantener fila vs omitir) — default **mantener**.

---

## Estados del job

`queued` → `running` → `completed` | `failed`

---

## Servicio runner (contrato interno)

```text
run_clean_job(user_or_service, project, version, file, *, dry_run=False, idempotency_key=None)
  → OperationResult { job_id, status, metrics, artifact_refs, errors }
```

- Usado por vistas HTML.  
- Mismo entrypoint que usará [`PLATFORM_API`](../PLATFORM_API.md) (`kind=file_clean`) **después** de FILE_OPS.  
- No pasar `request` al dominio; pasar identidad ya resuelta.

---

## API futura (referencia, no implementar ahora)

| Entrada | Salida |
|---------|--------|
| `kind=file_clean`, slug, `version=published`, `file` | `job_id`, `status`, `output_url`, `report_url` (log), `content_hash` in/out |

---

## Criterio de aceptación

- [x] Solo versión publicada en run productivo  
- [x] Preview + run completo  
- [x] Descarga output + log  
- [x] Runner invocable sin vista (`run_clean_job`)  
- [x] Idempotency-Key soportada a nivel servicio (header opcional en vistas)  
- [x] Secuencia `{seq}` reinicia por job; change log registra `replace_map` / `replace` / `compose`

## Implementación

| Pieza | Ruta |
|-------|------|
| Modelo | `apps/file_clean/models.py` → `CleanJob` |
| Motor | `apps/file_clean/run/services/clean_engine_service.py` |
| Output | `apps/file_clean/run/services/clean_output_service.py` |
| Runner | `apps/file_clean/run/services/clean_run_service.py` → `run_clean_job` |
| UI | `templates/file_clean/run/` · URLs `/ejecutar/` |
