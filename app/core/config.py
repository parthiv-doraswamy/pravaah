"""Typed application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings; secrets belong in environment variables, never source control."""

    app_name: str = "PRAVAAH API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://pravaah:pravaah@localhost:5432/pravaah"
    jwt_secret_key: str = Field(
        default="local-development-only-change-this-secret-before-deployment", min_length=32
    )
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def reject_default_secret_outside_development(self) -> "Settings":
        """Prevent accidental use of the bundled development signing key in production."""
        if self.app_env.lower() not in {"development", "test"} and self.jwt_secret_key.startswith(
            "local-development-only-"
        ):
            raise ValueError("Set a unique JWT_SECRET_KEY outside development and test environments")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        """Parse a comma-separated CORS origin list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache

def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
