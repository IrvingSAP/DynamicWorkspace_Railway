import logging

from django.conf import settings

from apps.core.services.operation_result import OperationResult

logger = logging.getLogger(__name__)


def send_email(
    *,
    to: list[str],
    subject: str,
    body: str,
    reply_to: str | None = None,
) -> OperationResult:
    if not to:
        return OperationResult.failure(
            "validation_form",
            "No se pudo enviar el mensaje. Intente más tarde.",
        )

    delivery = getattr(settings, "EMAIL_DELIVERY", "console")

    try:
        if delivery == "resend":
            return _send_via_resend(to=to, subject=subject, body=body, reply_to=reply_to)
        return _send_via_console(to=to, subject=subject, body=body, reply_to=reply_to)
    except Exception:
        logger.exception("email_delivery failed delivery=%s to=%s", delivery, to)
        return OperationResult.failure(
            "unexpected",
            "No se pudo enviar el mensaje. Intente más tarde.",
        )


def _send_via_console(
    *,
    to: list[str],
    subject: str,
    body: str,
    reply_to: str | None,
) -> OperationResult:
    print("--- DynamicWorkspace email (console) ---")
    print(f"To: {', '.join(to)}")
    if reply_to:
        print(f"Reply-To: {reply_to}")
    print(f"Subject: {subject}")
    print(body)
    print("--- end email ---")
    return OperationResult.success()


def _send_via_resend(
    *,
    to: list[str],
    subject: str,
    body: str,
    reply_to: str | None,
) -> OperationResult:
    import resend

    api_key = getattr(settings, "RESEND_API_KEY", "")
    if not api_key:
        logger.error("RESEND_API_KEY is not configured")
        return OperationResult.failure(
            "unexpected",
            "No se pudo enviar el mensaje. Intente más tarde.",
        )

    resend.api_key = api_key
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "onboarding@resend.dev")

    params: dict = {
        "from": from_email,
        "to": to,
        "subject": subject,
        "text": body,
    }
    if reply_to:
        params["reply_to"] = reply_to

    resend.Emails.send(params)
    return OperationResult.success()
