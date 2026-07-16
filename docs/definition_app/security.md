# apps.security

Wizard HTTP de autenticación: login, verificación por correo, TOTP y reset 2FA.

---

## Propósito

Gestionar el acceso al sistema sin registro público. El usuario completa correo + 2FA en el primer login.

---

## Responsabilidades

| Sí | No |
|----|-----|
| Login, correo, QR/TOTP, reset 2FA | Modelo `UserProfile` (→ `apps.accounts`) |
| Sesión intermedia `security_pending_user_id` | Permisos por proyecto |
| Plantillas de seguridad | Dashboard ni proyectos |

---

## Estructura prevista

```
apps/security/
├── views.py
├── urls.py
├── services/
│   ├── login_flow.py
│   ├── email_confirmation.py
│   ├── profile_routing.py
│   ├── security_session.py
│   ├── totp_utils.py
│   └── totp_reset.py
└── templates/security/
```

---

## URLs

| URL | Nombre | Descripción |
|-----|--------|-------------|
| `/ingresar/` | `security:login` | Credenciales |
| `/seguridad/correo/` | `security:email_code` | Código email |
| `/seguridad/totp-config/` | `security:totp_setup` | QR 2FA |
| `/seguridad/totp/` | `security:totp` | Validar TOTP |
| `/seguridad/actualizar-2fa/` | `security:actualizar_2fa` | Reset 2FA |
| `/seguridad/cancelar/` | `security:cancel` | Cancelar wizard |

> No existe `/registro/` público.

---

## Reglas

- Issuer TOTP: `DynamicWorkspace`
- Sin `login()` completo hasta TOTP válido
- Estado entre pasos en sesión, no en cookies persistentes

---

## Dependencias

- `apps.accounts` — `UserProfile`
- `apps.core` — `email_delivery`

## Fase

**Fase 0**.

## Documentos relacionados

- [`accounts.md`](accounts.md)
- [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md) — flujos funcionales
- [`../security/GUIA_IMPLEMENTACION_SEGURIDAD.md`](../security/GUIA_IMPLEMENTACION_SEGURIDAD.md) — implementación
- Prototipos: [`../../prototype/security/`](../../prototype/security/)
