# apps.core

Utilidades compartidas, decoradores, servicios transversales y mixins.

---

## Propósito

Centralizar código reutilizable que no pertenece a una app de dominio específica.

---

## Responsabilidades

| Sí | No |
|----|-----|
| Decoradores (`security_complete_required`, `project_permission_required`) | Modelos de negocio |
| Servicio de correo (`email_delivery`) | Vistas de pantalla |
| Mixins de permisos | Lógica de proyectos o registros |
| Helpers de validación genéricos | Configuración Django (va en `settings.py`) |

---

## Módulos previstos

```
apps/core/
├── decorators.py
├── mixins.py
├── services/
│   ├── email_delivery.py
│   └── operation_result.py   # Al iniciar desarrollo — ver UI_MESSAGES.md §9
└── utils.py
```

## Servicios transversales (al implementar)

| Módulo | Responsabilidad | Documento |
|--------|-----------------|-----------|
| `operation_result.py` | `OperationResult`, mapa `error_code` → texto §3 | [`UI_MESSAGES.md`](UI_MESSAGES.md) §2, §9 |
| `email_delivery.py` | Envío de correo | Este doc § abajo |

Los servicios de dominio (`apps.company.services`, etc.) **consumen** el contrato de `OperationResult`; no duplican textos ni códigos.

---

## Servicio de correo

Implementación: `apps/core/services/email_delivery.py`.

| Entorno | `EMAIL_DELIVERY` | Comportamiento |
|---------|------------------|----------------|
| **Desarrollo** (`DEBUG=True`) | `console` (forzado en settings) | Imprime el mensaje en la terminal del `runserver`. Códigos de seguridad visibles ahí; no requiere Resend ni buzón real. |
| **Producción** (`DEBUG=False`) | `resend` (por defecto; variable de entorno) | Envío real vía API Resend (`RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`). |

> **Solo desarrollo:** con `DEBUG=True`, `settings.py` ignora `EMAIL_DELIVERY` del `.env` y siempre usa `console`. En producción no aplica este atajo.

Detalle del flujo de códigos: [`../security/GUIA_IMPLEMENTACION_SEGURIDAD.md`](../security/GUIA_IMPLEMENTACION_SEGURIDAD.md) §5.3.

---

## Dependencias

Ninguna app de dominio. Consumida por `accounts`, `security`, `projects`, etc.

---

## Fase

**Fase 0** — fundación.

## Documentos relacionados

- [`CONVENCIONES.md`](CONVENCIONES.md)
- [`../security/GUIA_IMPLEMENTACION_SEGURIDAD.md`](../security/GUIA_IMPLEMENTACION_SEGURIDAD.md)
