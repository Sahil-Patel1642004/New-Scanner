import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        ("postgresql://user:pass@db.example.com/licensing", "postgresql+psycopg://user:pass@db.example.com/licensing"),
        ("postgres://user:pass@db.example.com/licensing", "postgresql+psycopg://user:pass@db.example.com/licensing"),
    ],
)
def test_normalizes_render_postgres_urls(database_url: str, expected: str) -> None:
    settings = Settings(_env_file=None, database_url=database_url)
    assert settings.database_url == expected


def test_production_rejects_development_secrets_and_mock_mail() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://user:pass@db.example.com/licensing",
            admin_password="ChangeMe123!",
            secret_key="development-secret-key-change-me",
            email_provider="mock",
            cors_origins=["https://admin.example.com"],
        )


def test_production_accepts_tls_postgres_and_smtp_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://user:pass@db.example.com/licensing",
        admin_email="admin@example.com",
        admin_password="production-admin-password-strong",
        secret_key="a-distinct-production-secret-key-over-32-chars",
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="mailer",
        smtp_password="smtp-secret",
        smtp_from_email="noreply@example.com",
        smtp_starttls=True,
        smtp_use_ssl=False,
        cors_origins=["https://admin.example.com"],
    )

    assert settings.environment == "production"
    assert settings.smtp_password.get_secret_value() == "smtp-secret"


@pytest.mark.parametrize("origin", ["https://", "https://admin.example.com/path"])
def test_production_rejects_invalid_https_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql://db.example.com/licensing",
            admin_email="admin@example.com",
            admin_password="production-admin-password-strong",
            secret_key="a-distinct-production-secret-key-over-32-chars",
            email_provider="smtp",
            smtp_host="smtp.example.com",
            smtp_from_email="noreply@example.com",
            cors_origins=[origin],
        )