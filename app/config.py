from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    github_token: str | None = Field(default=None, validation_alias="GITHUB_TOKEN")
    github_api_url: str = Field(
        default="https://api.github.com",
        validation_alias="GITHUB_API_URL",
    )
    github_api_version: str = Field(
        default="2022-11-28",
        validation_alias="GITHUB_API_VERSION",
    )
    results_per_topic: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias="RESULTS_PER_TOPIC",
    )
    report_top_n: int = Field(
        default=5,
        ge=1,
        le=100,
        validation_alias="REPORT_TOP_N",
    )
    request_timeout: float = Field(
        default=20.0,
        gt=0,
        validation_alias="REQUEST_TIMEOUT",
    )
    request_delay: float = Field(
        default=1.0,
        ge=0.0,
        validation_alias="REQUEST_DELAY",
    )
    max_rate_limit_wait_seconds: float = Field(
        default=300.0,
        ge=0.0,
        validation_alias="MAX_RATE_LIMIT_WAIT_SECONDS",
    )
    rate_limit_max_retries: int = Field(
        default=2,
        ge=0,
        validation_alias="RATE_LIMIT_MAX_RETRIES",
    )
    gmail_user: str | None = Field(
        default=None,
        validation_alias="GMAIL_USER",
    )
    gmail_app_password: str | None = Field(
        default=None,
        validation_alias="GMAIL_APP_PASSWORD",
    )
    email_recipient: str | None = Field(
        default=None,
        validation_alias="EMAIL_RECIPIENT",
    )
    email_notifications_enabled: bool = Field(
        default=False,
        validation_alias="EMAIL_NOTIFICATIONS_ENABLED",
    )
    enable_etag_cache: bool = Field(
        default=True,
        validation_alias="ENABLE_ETAG_CACHE",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
