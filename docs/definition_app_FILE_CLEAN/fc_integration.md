# FILE CLEAN — Integración transversal

> **Archivo:** `fc_integration.md`  
> **Producto:** [`../FILE_CLEAN.md`](../FILE_CLEAN.md)  
> **Estado:** borrador

---

## 1. Kind y chasis

| Ítem | Valor |
|------|--------|
| `Project.project_kind` | `file_clean` |
| Label UI | **File Clean** (Title Case, como menú) |
| App Django (objetivo) | `apps/file_clean/` |
| Namespace URLs | `file_clean:` |
| Prefijo | `/app/file-clean/` |

---

## 2. Roles

Mapa PA / ED / CO / GE — ver [`../FILE_CLEAN.md`](../FILE_CLEAN.md) §10.  
Ejecución (GE) alineada a Gate/Pipe para que PLATFORM_API pueda mapear “servicio ejecutor” → permiso GE.

---

## 3. Reuso DMS

| Componente | Uso |
|------------|-----|
| Source file types / parsers | Perfil de lectura |
| Intake / sample limits | Upload de job |
| Rule operators | Implementación de `code` de limpieza |
| Execution job patterns | Estados, storage, TTL |
| UI_MESSAGES / error_code | Respuestas servicio |

**No reusar:** TargetProfile, field mapping N:1 de negocio, publish de mapping ETL.

---

## 4. Encadenamiento (MVP manual)

```text
Clean (descarga output) → usuario sube a Gate / Pipe / Match
```

Fase posterior (Watch / PLATFORM_API / pipelines): pasar artifact por referencia sin re-upload.

---

## 5. PLATFORM API (fase posterior a FILE_OPS)

**Decisión de producto:** implementar API al **finalizar** las nuevas apps FILE_OPS. Clean nace listo:

| Requisito | Estado en diseño Clean |
|-----------|------------------------|
| `kind=file_clean` | Sí |
| Runner sin `request` HTTP de vista | Obligatorio en M5 |
| Artifacts `output` + `report` (log) | Sí |
| Solo `version=published` | Sí |
| Idempotency a nivel job | Diseñado en M5 |
| Auth máquina | Fuera de Clean; capa PLATFORM_API |

Contrato alineado a [`../PLATFORM_API.md`](../PLATFORM_API.md) §5 y §8 (matriz I/O).

---

## 6. Sidebar / dashboard / público

Cuando se implemente:

- Ítem menú **File Clean** (Title Case).  
- KPI / recientes en dashboard UF (patrón Gate).  
- Mención en guía pública / servicios (oleada ops).

---

## 7. Mensajes UI

Seguir [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md): servicios retornan `ok` / `error_code` / `user_message` / `errors`; vistas PRG + `messages.*`.

Prefijo sugerido de códigos: `file_clean_*` o reuso de códigos DMS donde el significado sea idéntico.

---

## 8. Checklist de integración

- [ ] Kind en `Project.KIND_CHOICES` + migraciones  
- [ ] URLs montadas bajo `/app/`  
- [ ] Sidebar + `app_nav_active`  
- [ ] Runner testeable sin vista  
- [ ] Documentado en PLATFORM_API inventario de kinds  
- [ ] Sin desplegar API hasta cierre oleada FILE_OPS
