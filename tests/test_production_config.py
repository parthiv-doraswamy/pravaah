"""Production configuration guard regression tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError, match="unique JWT_SECRET_KEY"):
        Settings(
            app_env="production",
            jwt_secret_key="local-development-only-change-this-secret-before-deployment",
            cors_origins="https://pravaah.example.test",
        )


@pytest.mark.parametrize(
    "origins",
    ["*", "", "http://pravaah.example.test", "https://pravaah.example.test,*"],
)
def test_production_rejects_unsafe_cors_origin_configuration(origins):
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="unique-production-signing-secret-for-ci-123",
            cors_origins=origins,
        )


def test_production_accepts_explicit_https_frontend_origin():
    settings = Settings(
        app_env="production",
        jwt_secret_key="unique-production-signing-secret-for-ci-123",
        cors_origins="https://pravaah.example.test",
    )
    assert settings.allowed_origins == ["https://pravaah.example.test"]
