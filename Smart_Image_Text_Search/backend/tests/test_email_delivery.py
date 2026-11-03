from __future__ import annotations

from datetime import date
from smtplib import SMTPAuthenticationError

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.security import encrypt_product_key, get_password_hash
from app.core.config import settings
from app.email_delivery import EmailDeliveryError, send_email
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AdminUser, Customer, Product

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def admin_token() -> str:
    db = SessionLocal()
    db.query(AdminUser).delete()
    db.add(AdminUser(email="admin@example.com", password_hash=get_password_hash("StrongPass123!"), is_active=True))
    db.commit()
    db.close()
    login = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    return login.json()["access_token"]


def test_send_licence_email_records_delivery(monkeypatch) -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    token = admin_token()

    db = SessionLocal()
    customer = Customer(name="Test Customer", email="customer@example.com", company_name="Acme")
    product = Product(name="Prakshal-Scanora Search", sku="SCANORA-SEARCH", description="Search product")
    db.add_all([customer, product])
    db.commit()
    db.refresh(customer)
    db.refresh(product)

    from app.models import Licence

    licence = Licence(
        customer_id=customer.id,
        product_id=product.id,
        licence_type="ONE_YEAR",
        product_key_hash="hash-1",
        product_key_ciphertext=encrypt_product_key("SCANORA-ABCD-1234-5678"),
        product_key_preview="SCANORA-ABCD-1234-****",
        issue_date=date(2026, 11, 2),
        expiry_date=date(2027, 11, 2),
        start_date=date(2026, 11, 2),
        status="UNUSED",
        activation_state="UNUSED",
        administrative_state="ENABLED",
        expiry_state="VALID",
        max_devices=1,
    )
    db.add(licence)
    db.commit()
    db.refresh(licence)
    db.close()

    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr("app.api.v1.licences.send_email", lambda *_args, **_kwargs: "<accepted@example.test>")

    response = client.post(
        f"/api/v1/licences/{licence.id}/send-email",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["delivery_status"] == "accepted"
    assert payload["recipient"] == "customer@example.com"

    log_response = client.get("/api/v1/email-logs", headers={"Authorization": f"Bearer {token}"})
    assert log_response.status_code == 200, log_response.text
    logs = log_response.json()
    assert len(logs) >= 1
    assert logs[0]["recipient"] == "customer@example.com"
    assert logs[0]["status"] == "ACCEPTED"


def test_failed_email_delivery_is_recorded(monkeypatch) -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    token = admin_token()

    db = SessionLocal()
    customer = Customer(name="Test Customer", email="failed@example.com")
    product = Product(name="Prakshal-Scanora Search", sku="SCANORA-SEARCH", description="Search product")
    db.add_all([customer, product])
    db.commit()
    db.refresh(customer)
    db.refresh(product)
    from app.models import Licence

    licence = Licence(
        customer_id=customer.id,
        product_id=product.id,
        licence_type="ONE_YEAR",
        product_key_hash="failed-hash",
        product_key_ciphertext=encrypt_product_key("SCANORA-ABCD-1234-5679"),
        product_key_preview="SCANORA-ABCD-****",
        issue_date=date(2026, 11, 2),
        expiry_date=date(2027, 11, 2),
        start_date=date(2026, 11, 2),
        status="UNUSED",
        activation_state="UNUSED",
        administrative_state="ENABLED",
        expiry_state="VALID",
        max_devices=1,
    )
    db.add(licence)
    db.commit()
    db.refresh(licence)
    licence_id = licence.id
    db.close()

    def reject_email(*_args, **_kwargs):
        raise EmailDeliveryError("SMTP rejected the message")

    monkeypatch.setattr("app.api.v1.licences.send_email", reject_email)
    response = client.post(
        f"/api/v1/licences/{licence_id}/send-email",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 502

    db = SessionLocal()
    try:
        from app.models import EmailLog

        log = db.query(EmailLog).filter(EmailLog.licence_id == licence_id).one()
        assert log.status == "FAILED"
        assert log.last_error == "SMTP rejected the message"
    finally:
        db.close()


def test_smtp_delivery_uses_starttls_auth_and_multipart_message(monkeypatch) -> None:
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self, context):
            calls.append(("starttls", context))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            calls.append(("send", message.get_content_type(), message["To"], message["Subject"], message["Message-ID"], message["Date"]))
            return {}

    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "mailer")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("smtp-password"))
    monkeypatch.setattr(settings, "smtp_from_email", "noreply@example.test")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_timeout_seconds", 12)
    monkeypatch.setattr("app.email_delivery.smtplib.SMTP", FakeSMTP)

    message_id = send_email("customer@example.test", "Licence", "Plain body", "<p>HTML body</p>")

    assert message_id
    assert calls[0] == ("connect", "smtp.example.test", 587, 12)
    assert calls[1][0] == "starttls"
    assert calls[2] == ("login", "mailer", "smtp-password")
    assert calls[3][:4] == ("send", "multipart/alternative", "customer@example.test", "Licence")
    assert calls[3][4].endswith("@example.test>")
    assert calls[3][5]


def test_smtp_auth_failure_reports_safe_code_without_credentials(monkeypatch) -> None:
    class RejectingSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self, **_kwargs):
            pass

        def login(self, *_args):
            raise SMTPAuthenticationError(535, b"authentication rejected")

    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "mailer@example.test")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("never-log-this-password"))
    monkeypatch.setattr(settings, "smtp_from_email", "mailer@example.test")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_timeout_seconds", 12)
    monkeypatch.setattr("app.email_delivery.smtplib.SMTP", RejectingSMTP)

    try:
        send_email("customer@example.test", "Licence", "Plain body", "<p>HTML body</p>")
    except EmailDeliveryError as error:
        assert str(error) == "SMTP delivery failed (SMTPAuthenticationError during authentication, code 535)."
        assert "never-log-this-password" not in str(error)
    else:
        raise AssertionError("SMTP authentication failure should be reported")
