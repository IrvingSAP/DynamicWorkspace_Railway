# Módulo 5 — Ejecución / Job (FILE CLEAN)

> **App:** File Clean  
> **Estado:** borrador de definición  
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
  → Aplicar reglas en orden
  → Serializar salida (mismo file_type / encoding destino de regla)
  → Persistir CleanJob + artifacts
  → Mostrar métricas + descargas
```

### Preview

- N primeras filas antes/después.  
- No persiste artifact definitivo (o marca `dry_run`).  
- GE/PA/ED según roles.

---

## Artifacts

| Artifact | Descripción |
|----------|-------------|
| `input` | Archivo original (TTL como samples/jobs DMS) |
| `output` | Archivo limpio descargable |
| `change_log` | JSON/CSV: fila, campo, regla, before, after |
| `metrics` | filas leídas, filas escritas, cambios, dedupe count, duración |

---

## Estados del job

`queued` → `running` → `completed` | `failed`

- Fallo de parseo / I/O → `failed`, sin `output` engañoso.  
- Reglas que dejan fila vacía: política explícita (mantener fila vs omitir) — default **mantener**.

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

- [ ] Solo versión publicada en run productivo  
- [ ] Preview + run completo  
- [ ] Descarga output + log  
- [ ] Runner invocable sin vista (test de servicio)  
- [ ] Idempotency-Key soportada a nivel servicio (aunque UI no la envíe aún)
