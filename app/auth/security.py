"""Password hashing and short-lived signed access tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with the recommended Argon2 configuration."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password safely; missing hashes never authenticate."""
    if not password_hash:
        return False
    return _password_hash.verify(password, password_hash)


def create_access_token(subject: str, role: str) -> str:
    """Create a signed access token with subject, role, issue, and expiry claims."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature, algorithm, and expiry before returning token claims."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
