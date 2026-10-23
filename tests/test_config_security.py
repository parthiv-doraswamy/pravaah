"""Regression tests for strict production security configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_settings(cors_origins: str) -> Settings:
    return Settings(
        app_env="production",
        cors_origins=cors_origins,
        jwt_secret_key="test-only-production-secret-value-123456789",
    )


def test_production_accepts_explicit_https_origins() -> None:
    settings = _production_settings(
        "https://pravaah-web.onrender.com,https://admin.example.org:8443"
    )

    assert settings.allowed_origins == [
        "https://pravaah-web.onrender.com",
        "https://admin.example.org:8443",
    ]


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "https://*.example.org",
        "http://pravaah-web.onrender.com",
        "https://pravaah-web.onrender.com/",
        "https://pravaah-web.onrender.com/path",
        "https://user:password@example.org",
        "https://example.org?debug=true",
        "https://example.org#fragment",
        "http://localhost:5173",
        "https://example.org,",
        "https://example.org, ,https://admin.example.org",
        "https://example.org:invalid",
    ],
)
def test_production_rejects_unsafe_or_malformed_origins(origins: str) -> None:
    with pytest.raises(ValidationError):
        _production_settings(origins)


def test_production_rejects_bundled_development_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            cors_origins="https://pravaah-web.onrender.com",
        )


def test_development_can_keep_localhost_cors_origin() -> None:
    settings = Settings(app_env="development", cors_origins="http://localhost:5173")

    assert settings.allowed_origins == ["http://localhost:5173"]
