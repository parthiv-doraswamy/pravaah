"""Typed application settings loaded from environment variables."""

from functools import lru_cache
from urllib.parse import urlsplit

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
    evidence_storage_dir: str = "./var/uploads"
    evidence_max_upload_bytes: int = 10485760

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_security_settings(self) -> "Settings":
        """Reject unsafe JWT defaults and permissive/malformed production CORS origins."""
        production = self.app_env.strip().lower() == "production"
        if not production and self.app_env.lower() not in {"development", "test"}:
            raise ValueError("APP_ENV must be development, test, or production")
        if not production:
            return self

        if self.jwt_secret_key.startswith("local-development-only-"):
            raise ValueError("Set a unique JWT_SECRET_KEY outside development and test environments")

        raw_origins = self.cors_origins.split(",")
        origins = [origin.strip() for origin in raw_origins]
        if not origins or any(not origin for origin in origins):
            raise ValueError("CORS_ORIGINS must contain a comma-separated list of explicit origins")

        for origin in origins:
            if origin == "*" or "*" in origin:
                raise ValueError("Wildcard CORS origins are not allowed in production")
            try:
                parsed = urlsplit(origin)
                # Accessing .port validates malformed port values.
                _ = parsed.port
            except ValueError:
                raise ValueError("CORS_ORIGINS contains a malformed origin") from None
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError(
                    "Production CORS origins must be explicit HTTPS origins without paths, "
                    "credentials, query strings, fragments, or localhost"
                )
        return self

    @property
    def allowed_origins(self) -> list[str]:
        """Parse a comma-separated CORS origin list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
