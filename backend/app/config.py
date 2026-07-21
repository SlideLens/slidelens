"""Application settings loaded from environment (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed ENV config. Missing required fields fail fast with a clear error."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "SlideLens"
    app_description: str = "AI deck review API"
    app_version: str = "0.1.0"

    # Postgres (assembled into ``database_url``). Optional ``DATABASE_URL`` wins
    # when set (sqlite in tests, one-off ops).
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "slidelens"
    db_user: str = "slidelens"
    db_password: SecretStr
    database_url_override: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
        description="Full SQLAlchemy URL; when set, ignores DB_* assembly",
    )

    redis_url: str
    secret_key: SecretStr
    environment: str = "development"
    enable_docs: bool | None = None
    # Comma-separated origins for local SPA; empty in production (single-domain Caddy, no CORS).
    cors_allow_origins: str = "http://localhost:5173"
    # Comma-separated emails granted the Администратор flag (unlimited Разборы,
    # bypasses free_reviews_left) on register/login — see app/auth.py.
    admin_emails: str = "admin@demo.com"

    @property
    def database_url(self) -> SecretStr:
        if self.database_url_override:
            return SecretStr(self.database_url_override)
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password.get_secret_value())
        return SecretStr(
            f"postgresql+asyncpg://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def docs_enabled(self) -> bool:
        if self.enable_docs is not None:
            return self.enable_docs
        return self.environment != "production"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.admin_emails.split(",") if e.strip())

    # Auth / JWT (API.md: access ~15 min, refresh ~30 days)
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    file_signature_expire_minutes: int = 15
    public_api_url: str = "http://localhost:8000"
    public_app_url: str = "http://localhost:5173"

    # LLM / VLM
    llm_api_key: SecretStr
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model_full: str = "gpt-4o"
    llm_model_screening: str = ""
    llm_model_transcription: str = "whisper-1"
    llm_timeout_seconds: int = 120
    llm_max_zooms_per_slide: int = 3

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    sentry_dsn: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr | None = None
    smtp_from: str = "noreply@example.com"

    # Storage / privacy
    storage_root: Path = Path("./storage")
    file_expire_days: int = 7

    # SPA dist (set STATIC_DIR=/app/static in Docker). Missing → API-only (Vite dev).
    static_dir: Path | None = None

    # Cost alert
    review_cost_alert_rub: float = 150.0


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
