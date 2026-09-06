# FILE REPAIR — Reparación asistida post-Gate

> **Nombre mnemotécnico:** `FILE_REPAIR`  
> Alias: *Reparador de archivos* · *Corrección auditada*  
> Archivo: [`docs/FILE_REPAIR.md`](FILE_REPAIR.md)  
> Estado: **pendiente de revisión** — validar aporte al sistema; decidir app hermana, **modo de Gate** o **unificación con File Clean**  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §4.2 (backlog)  
> Specs por módulo: *aún no*  
> Acoplado a: [`FILE_GATE.md`](FILE_GATE.md) · solapa motor con [`FILE_CLEAN.md`](FILE_CLEAN.md)

---

## 1. Resumen ejecutivo

**File Repair** corrige un archivo **a partir de los rechazos de File Gate**, con **trazabilidad** de cada cambio, y genera un `repaired` listo para volver a validar.

```text
original → Gate (REJECTED + informe)
        → File Repair (correcciones auditadas)
        → repaired → Gate → ACCEPTED
```

Cada corrección registra: regla, campo, valor original, valor corregido, usuario, fecha, versión. **No silenciosa.**

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Gate rechaza; el operador arregla en Excel sin traza ni reintento sistemático |
| **Solución** | Fixes dirigidos por el informe de errores + archivo reparado + auditoría |
| **Beneficio** | Menos fricción post-rechazo; compliance (quién cambió qué) |
| **Audiencia** | Operaciones, calidad, proveedores internos |

---

## 2. Función

| Hace | No hace |
|------|---------|
| Leer el informe de errores del job Gate | Inventar el contrato (Scout / perfil Gate) |
| Proponer o aplicar fixes campo a campo | Limpiar “por si acaso” sin error (Clean) |
| Registrar valor viejo → nuevo + quién/cuándo | Mapear a destino ERP (FilePipe) |
| Descargar `repaired` + log | Conciliar A vs B (Match) |

---

## 3. Frontera Clean vs Repair

| | **File Clean** | **File Repair** |
|--|----------------|-----------------|
| Momento | **Antes** de Gate (o Pipe/Match) | **Después** de un rechazo Gate |
| Disparador | Reglas genéricas del perfil Clean | Errores **concretos** del informe |
| Ejemplo | Trim, case, fecha ISO, dedupe | “Fila 42: `FECHA` no cumple `YYYY-MM-DD` → …” |
| Objetivo | Normalizar lote completo | Arreglar lo marcado y reintentar |

---

## 4. Ejemplos de uso

1. **Nómina rechazada por fechas** — 80 filas `31/12/25` vs contrato `YYYY-MM-DD` → conversión auditada solo ahí.  
2. **ID con ceros a la izquierda** — pad/trim ligado al código de error Gate.  
3. **Código de sucursal** — mapear alias (`BOG` → `11001`) con log; desconocidos a revisión humana.  
4. **Encoding / basura** — reemplazos puntuales del informe (no Clean global de 200k filas).  
5. **Ciclo** — proveedor sube → Gate REJECTED → Repair → descarga + auditoría → Gate ACCEPTED → Pipe/Match.

---

## 5. Formas posibles (a decidir en revisión)

| Opción | Cuándo tiene sentido |
|--------|----------------------|
| **Modo de Gate** | UX anclada al informe de rechazo; máxima claridad |
| **App hermana** | Ciclo propio (proyecto / versiones) si el volumen lo justifica |
| **Unificar con Clean** | Mismo motor de reglas + UI “calidad”; Repair = modo “dirigido por errores” |

La revisión debe **validar aporte** y elegir una de estas formas (o descartar / diferir).

---

## 6. Criterio de revisión

1. ¿El flujo post-Gate justifica producto propio vs “re-subir tras Excel”?  
2. ¿Reuso del motor de reglas Clean sin duplicar UI?  
3. ¿MVP: solo N códigos de error Gate, sin IA?  
4. ¿API-ready (`kind=file_repair`) alineado a PLATFORM_API?

---

## 7. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Backlog §4.2 |
| [`FILE_GATE.md`](FILE_GATE.md) | Origen del informe de rechazo |
| [`FILE_CLEAN.md`](FILE_CLEAN.md) | Motor / posible unificación |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Job futuro |

---

*Documento vivo. No abrir rama hasta revisión de aporte y forma (app / modo Gate / Clean).*
