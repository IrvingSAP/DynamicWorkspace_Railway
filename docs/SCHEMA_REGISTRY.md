# SCHEMA REGISTRY — Catálogo central de contratos de archivo

> **Nombre mnemotécnico:** `SCHEMA_REGISTRY`  
> Alias: *Registro de esquemas* · *Catálogo de contratos*  
> Archivo: [`docs/SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md)  
> Estado: **previsto (se desarrollará)** — **pendiente definir forma de trabajo**  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §4.4 (backlog)  
> Tipo: **capa de plataforma** (cambio de modelo mental vs contratos solo por proyecto)  
> Relacionado: [`PROFILE_SEED.md`](PROFILE_SEED.md) (clonar) · distinto de Master Catalog (códigos de negocio)

---

## 1. Resumen ejecutivo

Hoy los contratos viven **por proyecto** (perfil Gate, Source Pipe, etc.). **Schema Registry** es un **catálogo central** de contratos versionados que varias apps **consumen**:

```text
Schema Registry
    → Gate / Pipe / Reverse / Match / (Seed, Scout apply…)
```

Incluye: campos, tipos, longitudes, reglas de contenido, compatibilidad entre versiones, propietario, consumidores.

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | El mismo layout se redefine en silos; divergencia y breaking changes opacos |
| **Solución** | Una fuente de verdad versionada del “layout nómina v5” |
| **Beneficio** | Reuso, gobierno, aviso a consumidores ante cambios incompatibles |
| **Audiencia** | Arquitectura de datos, integradores, dueños de contrato |

---

## 2. Función

| Hace | No hace |
|------|---------|
| Publicar / versionar contratos de archivo | Sustituir Master Catalog de códigos de negocio |
| Listar consumidores y compatibilidad | Validar un archivo (sigue siendo Gate) |
| Ser fuente para sembrar perfiles | Ejecutar el Job ETL |

**Vs Profile Seed:** Seed **clona** una definición publicada a un borrador de proyecto; Registry es el **repositorio** del que muchas apps deberían leer a largo plazo.

---

## 3. Forma de trabajo (pendiente de decisión)

Se desarrollará; definir cómo se publica y consume:

| Forma | Descripción |
|-------|-------------|
| **Dentro de un pipeline** | Pasos “resolver contrato vN del registry” antes de Gate/Pipe |
| **Por API** | CRUD/consulta de contratos; apps resuelven `schema_id@version` |
| **Catálogo UI** | App/plataforma de gobierno (propietario, consumidores, changelog) |
| **Otras** | Import desde Gate publicado, export OpenAPI-like del layout, firmas |
| **Todas / híbrido** | UI de gobierno + API + resolución en runners |

Implica eventual migración del modelo “contrato solo en el proyecto”.

---

## 4. Ejemplos

1. **Mismo layout en Gate y Pipe** — `nomina_banco_v3` una vez; Gate valida y Pipe mapea sin redefinir 40 campos.  
2. **Breaking change** — v4 quita un campo → incompatibilidad marcada; consumidores avisados.  
3. **Onboarding Match** — “usar contrato A = extracto v2 del registry”.  
4. **Gobierno** — “¿quién es dueño del layout de pagos?” → propietario + lista de consumidores.

---

## 5. Relación con otras piezas

| Pieza | Pregunta |
|-------|----------|
| Watch / Scheduler / API | ¿Cuándo corre? |
| **Schema Registry** | ¿Con qué contrato versionado? |
| Archive | ¿Qué quedó registrado E2E? |
| Profile Seed | ¿Cómo clono hoy a un borrador? (puente hasta Registry maduro) |

---

## 6. Criterio antes de implementar

1. ¿Forma de trabajo (§3)?  
2. ¿Verticales §2 + Clean/Seed estables? (FILE_OPS: no bloquear MVP Clean/Split)  
3. ¿Migración desde contratos por proyecto?  
4. ¿Permisos de publicación de contrato (quién es “dueño”)?

---

## 7. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Backlog §4.4 |
| [`PROFILE_SEED.md`](PROFILE_SEED.md) | Siembra desde definición publicada |
| [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md) | Custodia E2E (otra capa) |
| [`FILE_GATE.md`](FILE_GATE.md) / Pipe / Match | Consumidores típicos |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Resolución de schema en Job remoto |

---

*Documento vivo. Desarrollo previsto; forma de trabajo abierta.*
