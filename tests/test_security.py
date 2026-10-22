"""Unit tests for password hashing and access-token integrity."""

import jwt
import pytest

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_verifies_only_the_correct_password() -> None:
    hashed = hash_password("Strong-test-password-42!")

    assert hashed != "Strong-test-password-42!"
    assert verify_password("Strong-test-password-42!", hashed)
    assert not verify_password("wrong-password", hashed)
    assert not verify_password("anything", None)


def test_access_token_contains_subject_and_role() -> None:
    token = create_access_token("12345678-1234-5678-1234-567812345678", "auditor")
    claims = decode_access_token(token)

    assert claims["sub"] == "12345678-1234-5678-1234-567812345678"
    assert claims["role"] == "auditor"
    assert "exp" in claims


def test_expired_token_is_rejected() -> None:
    from datetime import UTC, datetime, timedelta

    from app.core.config import get_settings

    expired = jwt.encode(
        {
            "sub": "12345678-1234-5678-1234-567812345678",
            "role": "auditor",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        get_settings().jwt_secret_key,
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)
