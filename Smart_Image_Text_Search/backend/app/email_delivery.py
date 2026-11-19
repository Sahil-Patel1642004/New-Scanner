from __future__ import annotations

import base64
import html
import logging
import smtplib
import ssl
import tempfile
import zipfile
from functools import lru_cache
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import httpx

from app.core.config import settings


class EmailDeliveryError(Exception):
    """Raised when the licence email cannot be sent."""


_INSTALLER_FILENAME = "SmartImageSearch-Setup.exe"
_MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024
_MAX_SOURCE_BYTES_TO_ZIP = 36 * 1024 * 1024
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _build_installer_zip() -> tuple[bytes | None, str]:
    """Download the configured installer and zip it without holding it all in memory."""
    if not settings.installer_download_url:
        raise EmailDeliveryError("INSTALLER_DOWNLOAD_URL is not configured.")

    try:
        with tempfile.TemporaryFile() as archive_file:
            with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                with httpx.stream(
                    "GET",
                    settings.installer_download_url,
                    follow_redirects=True,
                    timeout=httpx.Timeout(120.0, connect=20.0),
                ) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > _MAX_SOURCE_BYTES_TO_ZIP:
                        return None, "The licensed installer exceeds the email attachment size limit."
                    with archive.open(_INSTALLER_FILENAME, "w") as installer_entry:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            installer_entry.write(chunk)

            size = archive_file.tell()
            if size > _MAX_ATTACHMENT_BYTES:
                return None, f"The zipped installer is larger than {_MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB."
            archive_file.seek(0)
            return archive_file.read(), ""
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(f"Could not prepare the installer ZIP: {type(exc).__name__}.") from exc


def _email_content(
    customer_name: str,
    product_name: str,
    licence_type: str,
    product_key: str,
    start_date: object,
    expiry_date: object,
    download_url: str,
    attachment_note: str,
) -> tuple[str, str]:
    installer_step = (
        "Extract the attached ZIP and run the SmartImage Search installer."
        if not attachment_note
        else "Download the installer using the button below."
    )
    text_body = f"""Hello {customer_name},

Thank you for choosing {product_name}. Your licence is ready.

YOUR PRODUCT KEY
{product_key}

Licence type: {licence_type}
Valid from: {start_date}
Valid through: {expiry_date}

GETTING STARTED
1. {installer_step}
2. Open the application and enter your product key.
3. Select Activate to start using your licence.

Installer download: {download_url}
{attachment_note}

Please keep this email and your product key for your records. If you need help, reply to this email.

Kind regards,
The SmartImage Search Team
"""

    safe_values = [customer_name, product_name, licence_type, product_key, str(start_date), str(expiry_date)]
    safe = [html.escape(value) for value in safe_values]
    safe_url = html.escape(download_url, quote=True)
    html_body = f"""<!doctype html>
<html><body style="margin:0;background:#f4f6f8;font-family:Arial,sans-serif;color:#17202a">
  <div style="max-width:620px;margin:32px auto;background:#fff;border:1px solid #e5e9ef;border-radius:12px;overflow:hidden">
    <div style="background:#123b5d;padding:26px 32px;color:#fff">
      <div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;opacity:.8">SmartImage Search</div>
      <h1 style="font-size:24px;margin:10px 0 0">Your licence is ready</h1>
    </div>
    <div style="padding:28px 32px;line-height:1.6">
      <p>Hello {safe[0]},</p><p>Thank you for choosing <strong>{safe[1]}</strong>. Your licence is ready to activate.</p>
      <div style="background:#f2f7fb;border:1px solid #dce8f1;border-radius:8px;padding:18px;margin:22px 0">
        <div style="font-size:12px;color:#526575;text-transform:uppercase;letter-spacing:1px">Your product key</div>
        <div style="font-family:Consolas,monospace;font-size:19px;font-weight:bold;letter-spacing:1px;overflow-wrap:anywhere;margin-top:8px">{safe[3]}</div>
      </div>
      <table style="width:100%;border-collapse:collapse;margin:18px 0">
        <tr><td style="padding:7px 0;color:#526575">Licence type</td><td style="padding:7px 0;text-align:right"><strong>{safe[2]}</strong></td></tr>
        <tr><td style="padding:7px 0;color:#526575">Valid from</td><td style="padding:7px 0;text-align:right">{safe[4]}</td></tr>
        <tr><td style="padding:7px 0;color:#526575">Valid through</td><td style="padding:7px 0;text-align:right">{safe[5]}</td></tr>
      </table>
      <h2 style="font-size:17px;margin:24px 0 8px">Getting started</h2>
      <ol style="padding-left:22px"><li>{html.escape(installer_step)}</li><li>Open the application and enter your product key.</li><li>Select Activate to start using your licence.</li></ol>
      <p>{html.escape(attachment_note)}</p>
      <p style="margin:24px 0"><a href="{safe_url}" style="display:inline-block;background:#176b9b;color:#fff;text-decoration:none;padding:11px 17px;border-radius:6px;font-weight:bold">Download installer</a></p>
      <p style="font-size:13px;color:#526575">Please keep this email and your product key for your records. If you need help, reply to this email.</p>
      <p>Kind regards,<br><strong>The SmartImage Search Team</strong></p>
    </div>
  </div>
</body></html>"""
    return text_body, html_body


def _send_with_gmail_api(message: EmailMessage) -> str:
    """Send a MIME message through Gmail's HTTPS API using an OAuth refresh token."""
    if not all((settings.gmail_client_id, settings.gmail_client_secret, settings.gmail_refresh_token)):
        raise EmailDeliveryError(
            "GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN must be configured."
        )

    timeout = httpx.Timeout(float(settings.smtp_timeout_seconds))
    try:
        token_response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret.get_secret_value(),
                "refresh_token": settings.gmail_refresh_token.get_secret_value(),
                "grant_type": "refresh_token",
            },
            timeout=timeout,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise EmailDeliveryError("Google OAuth did not return an access token.")

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        response = httpx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw_message},
            timeout=timeout,
        )
        response.raise_for_status()
        message_id = response.json().get("id")
        if not message_id:
            raise EmailDeliveryError("Gmail API accepted no message ID in its response.")
        return message_id
    except EmailDeliveryError:
        raise
    except httpx.HTTPStatusError as exc:
        raise EmailDeliveryError(f"Gmail API request failed (HTTP {exc.response.status_code}).") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise EmailDeliveryError(f"Gmail API delivery failed ({type(exc).__name__}).") from exc


def send_licence_email(
    recipient: str,
    customer_name: str,
    product_name: str,
    licence_type: str,
    product_key: str,
    start_date: object,
    expiry_date: object,
) -> tuple[str, str, str]:
    subject = f"Your {product_name} licence and installer are ready"
    if settings.email_provider == "mock":
        return make_msgid(domain="mock.local"), subject, datetime.now(timezone.utc).isoformat()

    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailDeliveryError("SMTP_HOST and SMTP_FROM_EMAIL must be configured.")

    download_url = settings.installer_download_url or f"{settings.public_base_url.rstrip('/')}/api/v1/download/installer"
    try:
        zipped_installer, attachment_note = _build_installer_zip()
    except EmailDeliveryError as error:
        logger.warning("Installer ZIP unavailable for licence email (%s).", error)
        zipped_installer = None
        attachment_note = "The installer ZIP could not be attached. Use the download button below."
    if zipped_installer is None:
        attachment_note = f"{attachment_note} The installer is available using the download button below."

    text_body, html_body = _email_content(
        customer_name,
        product_name,
        licence_type,
        product_key,
        start_date,
        expiry_date,
        download_url,
        attachment_note,
    )
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=parseaddr(settings.smtp_from_email)[1].rsplit("@", 1)[-1] or None)
    message["Date"] = formatdate(localtime=True)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    if zipped_installer:
        message.add_attachment(
            zipped_installer,
            maintype="application",
            subtype="zip",
            filename="SmartImageSearch-Setup.zip",
        )

    if settings.email_provider == "gmail_api":
        provider_message_id = _send_with_gmail_api(message)
        sent_at = datetime.now(timezone.utc).isoformat()
        return provider_message_id, subject, sent_at

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
                stage = "TLS negotiation"
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                stage = "authentication"
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            stage = "message submission"
            refused = smtp.send_message(message)
            if recipient in refused:
                raise EmailDeliveryError("The SMTP server refused the recipient.")
    except EmailDeliveryError:
        raise
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailDeliveryError(f"SMTP delivery failed during {stage} ({type(exc).__name__}).") from exc

    sent_at = datetime.now(timezone.utc).isoformat()
    return message["Message-ID"], subject, sent_at
