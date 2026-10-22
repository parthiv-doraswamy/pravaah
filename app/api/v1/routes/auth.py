"""Login and authenticated user profile endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, verify_password
from app.core.config import get_settings
from app.db.session import get_db
from app.models.core import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Exchange credentials for an access token")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate an active user; return the same error for unknown email and bad password."""
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role),
        expires_in=int(timedelta(minutes=settings.access_token_expire_minutes).total_seconds()),
    )


@router.get("/me", response_model=UserResponse, summary="Get the current authenticated user")
def current_user(user: User = Depends(get_current_user)) -> User:
    return user
