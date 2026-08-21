# FILE WATCH — Recepción automática de archivos

> **Nombre mnemotécnico:** `FILE_WATCH`  
> Alias: *Bandeja vigilada* · *Ingestión por llegada*  
> Archivo: [`docs/FILE_WATCH.md`](FILE_WATCH.md)  
> Estado: **previsto (se desarrollará)** — **pendiente definir forma de trabajo**  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §10 · prioridad ⭐⭐⭐⭐⭐ (plataforma)  
> Tipo: **capa de plataforma** (no app de menú con wizard de campos)  
> Pareja: [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) · disparador hermano: [`PLATFORM_API.md`](PLATFORM_API.md)

---

## 1. Resumen ejecutivo

**File Watch** detecta que **llegó un archivo** y dispara el mismo Job que hoy se ejecuta a mano en la UI (Clean, Gate, Pipe, Match, Split/Merge, …).

```text
Watch (llegó un archivo)  ─┐
Scheduler / UI / API      ─┼→ Job (app + versión publicada) → notificar
```

Orígenes posibles: carpeta, SFTP, API/webhook, cloud storage, correo.

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Todo el pipeline depende de que un UF haga upload → ejecutar |
| **Solución** | Ingestión automática al detectar llegada + reglas de enrutado a proyecto/versión |
| **Beneficio** | Operación 24×7, menos error humano, mismo runner auditable |
| **Audiencia** | Ops, integración, tesorería / nómina |

---

## 2. Función

| Hace | No hace |
|------|---------|
| Vigilar un origen y detectar llegada | Definir reglas de negocio de cada app |
| Emparejar archivo → proyecto + versión publicada | Sustituir el historial de cada vertical |
| Idempotencia, reintentos, cuotas | Ser “otra app” de perfil/campos |
| Notificar (p. ej. Resend) | Reemplazar PLATFORM_API (son disparadores hermanos) |

**Disparador:** evento de **llegada** de archivo.

---

## 3. Forma de trabajo (pendiente de decisión)

Se desarrollará; hay que elegir **una o varias** de estas formas (pueden coexistir):

| Forma | Descripción |
|-------|-------------|
| **Dentro de un pipeline** | Paso “Watch” / origen al inicio de una cadena — ver [`FILE_PIPELINE.md`](FILE_PIPELINE.md) |
| **Por pedido de API** | Un webhook/API registra el archivo y encola el Job (solapa con PLATFORM_API) |
| **Monitor a la espera** | Listener persistente (carpeta / SFTP / cloud) que reacciona al drop |
| **Otras** | Correo entrante, cola de mensajería, bandeja por compañía, etc. |
| **Todas las anteriores** | Modelo unificado de “disparador → Job” con adaptadores por origen |

Documentar la decisión aquí y en FILE_OPS §18 cuando se cierre el spike.

---

## 4. Frontera con Scheduler

| **Watch** | **Scheduler** |
|-----------|---------------|
| Dispara por **llegada** de archivo | Dispara por **tiempo** o dependencia entre jobs |
| Drop impredecible del banco a las 14:37 | Cron diario 02:00 o “tras Job A” |

Implementar **junto o justo después** de Scheduler.

---

## 5. Ejemplos

1. **Extracto bancario** — SFTP `extracto_YYYYMMDD.csv` → Gate (versión publicada) → Pipe → notificar tesorería.  
2. **Nómina proveedor** — ZIP en carpeta vigilada → Split por sucursal → Gate por parte → correo si hay rechazos.  
3. **Combinado** — Watch recibe el archivo del día; Scheduler a las 06:00 reintenta fallidos o dispara Match de cierres.  
4. **Vs hoy** — mismo `run_*_job`; sin estar en la pantalla de Ejecutar.

---

## 6. Coste / riesgos

Alto en **ops y seguridad**: credenciales, cuotas, duplicados (mismo archivo dos veces), reintentos, notificaciones. No es solo UI.

---

## 7. Criterio antes de implementar

1. ¿Forma de trabajo elegida (tabla §3)?  
2. ¿Modelo de Job / Pipeline encadenable estable? — [`FILE_PIPELINE.md`](FILE_PIPELINE.md)  
3. ¿Idempotencia y tenancy claros?  
4. ¿Relación explícita con PLATFORM_API y Pipeline (`pipeline_id`)?

---

## 8. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Paraguas §10 |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación; Watch dispara `pipeline_id` |
| [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) | Disparo por tiempo / dependencia |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Disparo HTTP del mismo Job / Pipeline |

---

*Documento vivo. Desarrollo previsto; forma de trabajo abierta.*
