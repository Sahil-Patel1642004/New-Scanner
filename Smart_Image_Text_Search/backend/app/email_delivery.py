from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from app.core.config import settings


class EmailDeliveryError(Exception):
    pass


def send_email(recipient: str, subject: str, text_body: str, html_body: str) -> str:
    if settings.email_provider == "mock":
        if settings.environment.casefold() == "production":
            raise EmailDeliveryError("Mock email delivery is disabled in production.")
        return f"mock-{make_msgid().strip('<>')}"

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