from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from app.core.config import settings


class EmailDeliveryError(Exception):
    pass


def send_email(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
    attachment_path: str | None = None,
) -> str:
    """Send an email and return the Message-ID.

    In mock mode the message is not delivered but a mock Message-ID is returned.
    ``attachment_path`` is accepted for API compatibility but is intentionally
    ignored - the installer is too large (> 200 MB) for SMTP.  Instead, a
    download link is embedded in the email body by the caller.

    Supported providers (EMAIL_PROVIDER env var):
      - mock   : No delivery; returns a fake ID. Useful for development.
      - resend : Uses the Resend HTTP API (works on Render free tier, port 443).
      - smtp   : Direct SMTP (may be blocked on Render free tier, errno 101).
    """
    if settings.email_provider == "mock":
        if settings.environment.casefold() == "production":
            raise EmailDeliveryError("Mock email delivery is disabled in production.")
        return f"mock-{make_msgid().strip('<>')}"

    if settings.email_provider == "resend":
        return _send_via_resend(recipient, subject, text_body, html_body)

    # Default: SMTP
    return _send_via_smtp(recipient, subject, text_body, html_body)


def _send_via_resend(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> str:
    """Deliver email using the Resend HTTP API (port 443 - works everywhere)."""
    if not settings.resend_api_key:
        raise EmailDeliveryError(
            "RESEND_API_KEY is not configured. "
            "Sign up at https://resend.com and set RESEND_API_KEY in your environment variables."
        )

    from_email = settings.smtp_from_email or "noreply@resend.dev"

    try:
        import resend as resend_sdk  # type: ignore[import]
    except ImportError as exc:
        raise EmailDeliveryError(
            "The 'resend' Python package is not installed. "
            "Add 'resend>=2.0.0' to requirements.txt and redeploy."
        ) from exc

    try:
        resend_sdk.api_key = settings.resend_api_key
        params: resend_sdk.Emails.SendParams = {
            "from": from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
        response = resend_sdk.Emails.send(params)
        # response is a dict with an "id" key
        return response.get("id", "resend-unknown-id")
    except Exception as exc:
        raise EmailDeliveryError(f"Resend API delivery failed: {exc}") from exc


def _send_via_smtp(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> str:
    """Deliver email using direct SMTP (may be blocked on Render free tier)."""
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailDeliveryError("SMTP host and sender address are not configured.")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    sender_domain = parseaddr(settings.smtp_from_email)[1].rsplit("@", 1)[-1]
    message["Message-ID"] = make_msgid(domain=sender_domain or None)
    message["Date"] = formatdate(localtime=True)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    stage = "connection"
    try:
        if settings.smtp_use_ssl:
            connection = smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
        else:
            connection = smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            )

        with connection as smtp:
            if settings.smtp_starttls and not settings.smtp_use_ssl:
                stage = "STARTTLS negotiation"
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                stage = "authentication"
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            stage = "message submission"
            refused = smtp.send_message(message)
            if recipient in refused:
                raise EmailDeliveryError("The SMTP server refused the recipient.")
    except (smtplib.SMTPException, OSError) as error:
        details = [f"{type(error).__name__} during {stage}"]
        smtp_code = getattr(error, "smtp_code", None)
        error_number = getattr(error, "errno", None)
        if smtp_code is not None:
            details.append(f"code {smtp_code}")
        elif error_number is not None:
            details.append(f"errno {error_number}")
        raise EmailDeliveryError(f"SMTP delivery failed ({', '.join(details)}).") from error

    return message["Message-ID"]
