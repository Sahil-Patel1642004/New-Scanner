from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Prakshal-Scanora Licensing API"
    environment: str = "development"
    database_url: str = "sqlite:///./licensing_dev.db"
    admin_email: str = "admin@localhost"
    admin_password: str = "ChangeMe123!"
    secret_key: str = "development-secret-key-change-me"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    email_provider: str = "mock"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = Field(default=15, ge=1, le=60)
    licence_offline_grace_hours: int = Field(default=72, ge=0, le=720)

    @field_validator("database_url")
    @classmethod
    def use_psycopg3_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.email_provider not in {"mock", "smtp"}:
            raise ValueError("EMAIL_PROVIDER must be 'mock' or 'smtp'.")
        if self.smtp_use_ssl and self.smtp_starttls:
            raise ValueError("SMTP_USE_SSL and SMTP_STARTTLS cannot both be enabled.")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together.")

        if self.environment.casefold() != "production":
            return self

        if len(self.secret_key) < 32 or self.secret_key == "development-secret-key-change-me":
            raise ValueError("Production requires a unique SECRET_KEY of at least 32 characters.")
        if len(self.admin_password) < 12 or self.admin_password == "ChangeMe123!":
            raise ValueError("Production requires a unique ADMIN_PASSWORD of at least 12 characters.")
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Production requires PostgreSQL; run migrations before starting the API.")
        if self.email_provider != "smtp":
            raise ValueError("Production requires EMAIL_PROVIDER=smtp.")
        if not self.smtp_host or not self.smtp_from_email:
            raise ValueError("Production SMTP_HOST and SMTP_FROM_EMAIL are required.")
        if not self.smtp_use_ssl and not self.smtp_starttls:
            raise ValueError("Production SMTP must use TLS.")
        if not self.cors_origins or any(not self._is_production_origin(origin) for origin in self.cors_origins):
            raise ValueError("Production CORS_ORIGINS must contain HTTPS origins only.")
        return self

    @staticmethod
    def _is_production_origin(origin: str) -> bool:
        if origin != origin.strip():
            return False
        try:
            parsed = urlparse(origin)
            parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
