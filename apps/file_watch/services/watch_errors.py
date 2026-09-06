"""M8: catálogo error_code ↔ user_message (capas 2 y 3). El código no se muestra al usuario."""

from __future__ import annotations

VALIDATION_REQUIRED = "validation_required"
SLUG_TAKEN = "watch_slug_taken"
FORBIDDEN = "watch_forbidden"
INCOMPLETE = "watch_incomplete"
SOURCE_INVALID = "watch_source_invalid"
SECRET_MISSING = "watch_secret_missing"
SFTP_UNREACHABLE = "watch_sftp_unreachable"
NO_PUBLISHED = "watch_no_published_target"
FIRE_ROUTE_CONFLICT = "watch_fire_route_conflict"
ROUTE_CROSS_TENANT = "watch_route_cross_tenant"
INTAKE_UNSTABLE = "watch_intake_unstable"
INTAKE_TOO_LARGE = "watch_intake_too_large"
INTAKE_STORE_FAILED = "watch_intake_store_failed"
INTAKE_HASH_FAILED = "watch_intake_hash_failed"
DUPLICATE_CONTENT = "watch_duplicate_content"
QUOTA_PENDING = "watch_quota_pending"
QUOTA_DAILY = "watch_quota_daily"
QUOTA_BYTES = "watch_quota_bytes"
FIRE_FAILED = "watch_fire_failed"
INACTIVE = "watch_inactive"
NOTIFY_WEBHOOK_INVALID = "watch_notify_webhook_invalid"
NOTIFY_EMAIL_INVALID = "watch_notify_email_invalid"

OPAQUE_CODES = frozenset({ROUTE_CROSS_TENANT})

MESSAGES = {
    VALIDATION_REQUIRED: "Complete los campos obligatorios.",
    SLUG_TAKEN: "Ese código de bandeja ya existe en la compañía.",
    FORBIDDEN: "No tiene permiso para cambiar esta bandeja.",
    INCOMPLETE: (
        "Complete el origen (y el enrutado si dispara al llegar) para activar."
    ),
    SOURCE_INVALID: "La configuración del origen no es válida. Consulte la Ayuda.",
    SECRET_MISSING: "Indique la credencial del origen SFTP.",
    SFTP_UNREACHABLE: "No se pudo conectar al SFTP. Revise host, puerto y credencial.",
    NO_PUBLISHED: "El destino no tiene una versión publicada operativa.",
    FIRE_ROUTE_CONFLICT: (
        "«Al llegar» no es compatible con enrutado Diferir. "
        "Elija Job/Pipeline o cambie el disparo."
    ),
    INTAKE_UNSTABLE: "El archivo seguía cambiando y no se pudo ingerir.",
    INTAKE_TOO_LARGE: "El archivo supera el tamaño máximo permitido.",
    INTAKE_STORE_FAILED: "No se pudo guardar el archivo en storage. Inténtelo más tarde.",
    INTAKE_HASH_FAILED: "No se pudo calcular el hash del archivo.",
    DUPLICATE_CONTENT: (
        "Se omitió la llegada: el contenido ya fue ingerido en esta bandeja."
    ),
    QUOTA_PENDING: "Se omitió: hay demasiados lotes pendientes en la bandeja.",
    QUOTA_DAILY: "Se omitió: se alcanzó el máximo de llegadas del día.",
    QUOTA_BYTES: "Se omitió: se alcanzó el máximo de volumen del día.",
    FIRE_FAILED: "No se pudo encolar el Job al llegar el archivo.",
    INACTIVE: "La bandeja no está activa; no se dispara.",
    NOTIFY_WEBHOOK_INVALID: "El webhook debe empezar por https://.",
    NOTIFY_EMAIL_INVALID: "Un miembro marcado no tiene correo en su cuenta.",
}

CATALOG = [
    {
        "code": VALIDATION_REQUIRED,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[VALIDATION_REQUIRED],
    },
    {
        "code": SLUG_TAKEN,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[SLUG_TAKEN],
    },
    {
        "code": FORBIDDEN,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Modal",
        "user_message": MESSAGES[FORBIDDEN],
    },
    {
        "code": INCOMPLETE,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Modal",
        "user_message": MESSAGES[INCOMPLETE],
    },
    {
        "code": SOURCE_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline + alerta",
        "user_message": MESSAGES[SOURCE_INVALID],
    },
    {
        "code": SECRET_MISSING,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[SECRET_MISSING],
    },
    {
        "code": SFTP_UNREACHABLE,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Modal",
        "user_message": MESSAGES[SFTP_UNREACHABLE],
    },
    {
        "code": NO_PUBLISHED,
        "layer": "2",
        "layer_label": "2 y 3",
        "channel": "Inline / Lotes",
        "user_message": MESSAGES[NO_PUBLISHED],
    },
    {
        "code": FIRE_ROUTE_CONFLICT,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline + alerta",
        "user_message": MESSAGES[FIRE_ROUTE_CONFLICT],
    },
    {
        "code": INTAKE_UNSTABLE,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[INTAKE_UNSTABLE],
    },
    {
        "code": INTAKE_TOO_LARGE,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[INTAKE_TOO_LARGE],
    },
    {
        "code": INTAKE_STORE_FAILED,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[INTAKE_STORE_FAILED],
    },
    {
        "code": INTAKE_HASH_FAILED,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[INTAKE_HASH_FAILED],
    },
    {
        "code": DUPLICATE_CONTENT,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[DUPLICATE_CONTENT],
    },
    {
        "code": QUOTA_PENDING,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[QUOTA_PENDING],
    },
    {
        "code": QUOTA_DAILY,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[QUOTA_DAILY],
    },
    {
        "code": QUOTA_BYTES,
        "layer": "3",
        "layer_label": "3 · Intake",
        "channel": "Lotes",
        "user_message": MESSAGES[QUOTA_BYTES],
    },
    {
        "code": FIRE_FAILED,
        "layer": "3",
        "layer_label": "3 · Fire",
        "channel": "Lotes",
        "user_message": MESSAGES[FIRE_FAILED],
    },
    {
        "code": INACTIVE,
        "layer": "3",
        "layer_label": "3 · Fire",
        "channel": "Lotes",
        "user_message": MESSAGES[INACTIVE],
    },
    {
        "code": NOTIFY_WEBHOOK_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[NOTIFY_WEBHOOK_INVALID],
    },
    {
        "code": NOTIFY_EMAIL_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[NOTIFY_EMAIL_INVALID],
    },
]

MSG_REQUIRED = MESSAGES[VALIDATION_REQUIRED]
MSG_SLUG_TAKEN = MESSAGES[SLUG_TAKEN]
MSG_FORBIDDEN = MESSAGES[FORBIDDEN]
MSG_INCOMPLETE = MESSAGES[INCOMPLETE]
MSG_CREATED = "Bandeja creada correctamente."
MSG_UPDATED = "Bandeja actualizada."
MSG_PAUSED_OK = "Bandeja pausada."
MSG_RESUMED = "Bandeja reanudada."
MSG_ARCHIVED = "Bandeja archivada."
MSG_ACTIVATED = "Bandeja marcada como Activa."
MSG_NOTIFY_SAVED = "Avisos guardados correctamente."


def message_for(error_code: str) -> str:
    return MESSAGES.get(error_code or "", "")


def catalog_rows() -> list[dict]:
    return list(CATALOG)
