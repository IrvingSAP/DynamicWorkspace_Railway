# DATA PROFILER — Perfil estadístico de contenido

> **Nombre mnemotécnico:** `DATA_PROFILER`  
> Alias: *Profiler* · *Perfil de calidad de datos*  
> Archivo: [`docs/DATA_PROFILER.md`](DATA_PROFILER.md)  
> Estado: **pendiente de revisión** — validar si aporta valor diferencial al sistema antes de abrir `definition_app_*` / rama  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §4.1 (backlog)  
> Specs por módulo: *aún no* (`definition_app_DATA_PROFILER/` cuando se apruebe)  
> Hermano conceptual: [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) (estructura ≠ contenido)

---

## 1. Resumen ejecutivo

**Data Profiler** mide la **calidad y distribución del contenido** de un archivo. No inventa el layout (Scout), no limpia (Clean) y no valida contra un contrato (Gate).

```text
Scout → Data Profiler → Clean → Gate → …
```

Responde: *¿cómo están los datos?* (nulos, uniques, duplicados, longitudes, outliers, posibles PII, drift vs corridas anteriores).

```text
CLIENTE: 152.430 filas · 1.823 vacíos · 149.221 únicos · …
```

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Se modela o valida “a ciegas”: no se sabe si el lote viene incompleto, con formatos mixtos o con drift respecto a ayer |
| **Solución** | Informe estadístico por campo / archivo, comparable entre corridas |
| **Beneficio** | Decisiones informadas antes de Clean/Gate; menos rechazos sorpresa |
| **Audiencia** | Calidad de datos, operaciones, integradores |

---

## 2. Función (qué mide)

| Dimensión | Pregunta |
|-----------|----------|
| Completitud | ¿Cuántos nulos / vacíos por campo? |
| Cardinalidad | ¿Cuántos valores únicos? ¿Casi todos distintos? |
| Duplicados | ¿Hay filas o claves repetidas? |
| Longitudes / formatos | ¿IDs de 5 y de 20 caracteres? ¿Fechas raras? |
| Distribución | Top valores, rarezas, outliers |
| Riesgo | Posible PII; drift vs una corrida anterior |

---

## 3. Frontera Scout vs Profiler

| | **Structure Scout** | **Data Profiler** |
|--|---------------------|-------------------|
| Pregunta | ¿Qué estructura parece? | ¿Cómo son los datos? |
| Salida | Columnas, tipos, posiciones → sembrar perfil | Informe estadístico / alertas de calidad |
| No hace | No juzga “malo” el contenido | No propone el contrato de campos |

**Decisión de producto:** no fusionar con Scout.

---

## 4. Ejemplos de uso

1. **Nómina nueva del proveedor** — Scout detecta columnas. Profiler: `DOCUMENTO` 2 % vacíos, `SUCURSAL` solo 3 valores, `SALARIO` con outliers → antes de Clean/Gate.  
2. **Extracto bancario de 500k filas** — `FECHA` con 120 formatos distintos, `MONTO` con comas vs puntos → justifica reglas de Clean.  
3. **Tras Merge de tres meses** — drift: en marzo `CIUDAD` pasó de 40 a 200 únicos / más nulos.  
4. **Onboarding Gate** — “este campo parece obligatorio en la muestra (0 nulos)” → decisión de contrato informada.  
5. **PII / compliance** — columnas que parecen email, teléfono o documento → cuidado en historial/descargas.

---

## 5. Criterio de revisión (antes de desarrollar)

Validar con producto/ops:

1. ¿El informe aporta decisiones que hoy no se cubren con Scout + historial Gate?  
2. ¿App con `project_kind`, módulo de Scout, o job ad-hoc?  
3. ¿MVP acotable (formatos, métricas mínimas, sin “IA que adivina”)?  
4. ¿Encaja en Job encadenable / PLATFORM_API (`kind` tentativo)?

Si la revisión **no** valida aporte → archivar o fusionar alcance en Scout (documentar decisión aquí y en FILE_OPS).

---

## 6. Relación con la plataforma

| Pieza | Relación |
|-------|----------|
| Structure Scout | Upstream típico (estructura ya conocida o en paralelo) |
| File Clean / Gate | Downstream: Profiler informa; Clean/Gate actúan |
| Parsers DMS | Lectura de muestra / archivo |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Job profileable cuando exista la API |

---

## 7. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Backlog §4.1 |
| [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) | Frontera estructura vs contenido |
| [`FILE_CLEAN.md`](FILE_CLEAN.md) | Normalización post-perfil |
| [`FILE_GATE.md`](FILE_GATE.md) | Validación contra contrato |

---

*Documento vivo. Congelar alcance solo tras revisión de aporte.*
