from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter()


def _extract_client_meta(request: Request) -> dict[str, Any]:
    """Extract non-sensitive client metadata for server session tracking."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "device_name": request.headers.get("x-device-name"),
    }


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Customer Account",
    description="Registers a new customer account, assigns the default CUSTOMER role, and returns an authenticated session.",
)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    auth_service = AuthService(db)
    client_meta = _extract_client_meta(request)
    return auth_service.register_user(payload, client_meta=client_meta)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates by email or phone with Argon2id and enumeration protection, returning a new session.",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    auth_service = AuthService(db)
    client_meta = _extract_client_meta(request)
    return auth_service.authenticate(payload, client_meta=client_meta)


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate Refresh Token",
    description="Rotates opaque refresh token and issues a new access token under row-level database lock.",
)
def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RefreshTokenResponse:
    auth_service = AuthService(db)
    client_meta = _extract_client_meta(request)
    return auth_service.refresh_session(
        payload.refresh_token,
        client_meta=client_meta,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revokes the server-side authentication session identified by the refresh token. Safe to repeat.",
)
def logout(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> LogoutResponse:
    auth_service = AuthService(db)
    return auth_service.logout(payload.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current Authenticated User",
    description="Returns the profile of the currently authenticated user. Never exposes sensitive fields.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone=current_user.phone,
        status=current_user.status,
        created_at=current_user.created_at,
    )
