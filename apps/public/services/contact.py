import re

from django.conf import settings

from apps.core.services.email_delivery import send_email
from apps.core.services.operation_result import OperationResult

SUBJECT_CHOICES = {
    "demo": "Solicitar demostración",
    "acceso": "Solicitar acceso para mi compañía",
    "planes": "Consulta sobre planes",
    "soporte": "Soporte general",
    "otro": "Otro",
}

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def submit_contact_message(posted: dict) -> OperationResult:
    errors = _validate(posted)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos marcados; no se pudo enviar el mensaje.",
            errors=errors,
        )

    full_name = posted["full_name"].strip()
    email = posted["email"].strip()
    company_name = posted.get("company_name", "").strip()
    subject_key = posted["subject"].strip()
    message = posted["message"].strip()
    subject_label = SUBJECT_CHOICES[subject_key]

    body_lines = [
        "Nuevo mensaje desde el formulario de contacto",
        "",
        f"Nombre: {full_name}",
        f"Correo: {email}",
        f"Compañía: {company_name or '—'}",
        f"Asunto: {subject_label}",
        "",
        "Mensaje:",
        message,
    ]
    body = "\n".join(body_lines)

    recipient = getattr(
        settings,
        "PUBLIC_CONTACT_EMAIL",
        "contacto@dynamicworkspace.app",
    )
    mail_result = send_email(
        to=[recipient],
        subject=f"[DynamicWorkspace] {subject_label} — {full_name}",
        body=body,
        reply_to=email,
    )
    if not mail_result.ok:
        return mail_result

    return OperationResult.success(
        "Su mensaje se envió correctamente. Le responderemos pronto.",
    )


def _validate(posted: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    full_name = posted.get("full_name", "").strip()
    if not full_name:
        errors.setdefault("full_name", []).append("Ingrese su nombre completo.")
    elif len(full_name) > 120:
        errors.setdefault("full_name", []).append("El nombre es demasiado largo.")

    email = posted.get("email", "").strip()
    if not email:
        errors.setdefault("email", []).append("Ingrese su correo electrónico.")
    elif not EMAIL_RE.match(email):
        errors.setdefault("email", []).append("Ingrese un correo electrónico válido.")
    elif len(email) > 254:
        errors.setdefault("email", []).append("El correo es demasiado largo.")

    company_name = posted.get("company_name", "").strip()
    if len(company_name) > 160:
        errors.setdefault("company_name", []).append("El nombre de la compañía es demasiado largo.")

    subject = posted.get("subject", "").strip()
    if not subject:
        errors.setdefault("subject", []).append("Seleccione un asunto.")
    elif subject not in SUBJECT_CHOICES:
        errors.setdefault("subject", []).append("Seleccione un asunto válido.")

    message = posted.get("message", "").strip()
    if not message:
        errors.setdefault("message", []).append("Escriba su mensaje.")
    elif len(message) < 10:
        errors.setdefault("message", []).append("El mensaje es demasiado corto.")
    elif len(message) > 4000:
        errors.setdefault("message", []).append("El mensaje es demasiado largo.")

    return errors
