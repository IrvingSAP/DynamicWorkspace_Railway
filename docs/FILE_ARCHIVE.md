# FILE ARCHIVE — Custodia y trazabilidad E2E

> **Nombre mnemotécnico:** `FILE_ARCHIVE`  
> Alias: *Custodia de archivos* · *Expediente de proceso*  
> Archivo: [`docs/FILE_ARCHIVE.md`](FILE_ARCHIVE.md)  
> Estado: **previsto (se desarrollará)** — **pendiente definir forma de trabajo**  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §12 · prioridad ⭐⭐ (plataforma)  
> Tipo: **capa transversal** (no sustituye el historial de cada app)  
> Momento: cuando haya **pipelines multi-app** en producción

---

## 1. Resumen ejecutivo

Hoy cada app tiene **su** historial. **File Archive** unifica un proceso de punta a punta:

```text
Proceso #84921
Entrada:  nomina_2026_08.csv     SHA-256: …
Validación: PASSED (Gate v3)
Transformación: FilePipe v3
Salida:   nomina_erp_2026_08.txt SHA-256: …
Estado: COMPLETED
```

Responde: *¿Qué archivo de entrada produjo exactamente esta salida, con qué versiones y hashes?*

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Auditoría E2E implica rebuscar en 3–4 historiales distintos |
| **Solución** | Expediente único entrada → pasos → salida + hashes |
| **Beneficio** | Compliance, incidentes, respuesta a “¿procesaron *este* archivo?” |
| **Audiencia** | Finanzas, nómina, auditoría, ops |

---

## 2. Función

| Hace | No hace |
|------|---------|
| Expediente E2E (entrada → pasos → salida + hashes) | Reemplazar el historial operativo de cada app |
| Búsqueda por proceso, hash, fecha, cadena | Ejecutar Clean/Gate/Pipe |
| Retención / custodia según política | Editar reglas o perfiles |

**Vs historial por app:** el historial local cuenta la corrida de *esa* app; Archive cuenta el **viaje completo** del archivo.

---

## 3. Forma de trabajo (pendiente de decisión)

Se desarrollará; definir cómo se alimenta y consulta:

| Forma | Descripción |
|-------|-------------|
| **Dentro de un pipeline** | Cada paso del run escribe al expediente — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) |
| **Por API** | Consulta / registro de custodia vía PLATFORM_API o API de archive |
| **Agregador asíncrono** | Consume eventos de jobs completados de cada app |
| **Otras** | Export legal, WORM storage, retención por compañía |
| **Todas / híbrido** | Eventos automáticos + API de consulta + UI de expediente |

Priorizar cuando existan cadenas reales (p. ej. Clean → Gate → Pipe → Match).

---

## 4. Ejemplos

1. **Auditoría de nómina** — “El TXT del banco el día 5, ¿de qué CSV y qué versión de Pipe?”  
2. **Incidente** — salida mala → Archive muestra Gate v3 OK + Pipe v4 (no v3).  
3. **Compliance** — hashes entrada/salida N años sin rebuscar en 4 apps.  
4. **Cliente** — “¿Procesaron *este* archivo?” → búsqueda por SHA-256.

---

## 5. Relación con otras piezas

| Pieza | Pregunta |
|-------|----------|
| Watch / Scheduler / API | ¿Cuándo corrió? |
| Schema Registry | ¿Con qué contrato? |
| **Archive** | ¿Qué quedó registrado E2E? |

---

## 6. Criterio antes de implementar

1. ¿Forma de trabajo (§3)?  
2. ¿Hay al menos un pipeline multi-app en producción que lo justifique?  
3. ¿Política de retención y almacenamiento (Railway/S3)?  
4. ¿Quién puede ver expedientes (roles / compañía)?

---

## 7. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Paraguas §12 |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Runs E2E a custodiar |
| [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) | Contratos (otra capa) |

---

*Documento vivo. Desarrollo previsto; forma de trabajo abierta.*
