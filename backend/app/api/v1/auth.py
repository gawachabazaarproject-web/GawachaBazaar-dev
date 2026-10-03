"""Authentication endpoints.

Sign-up, sign-in, sign-out, email verification, password reset, Google
and phone OTP all happen client-side against Firebase Auth. The backend
only needs to (a) turn a verified Firebase identity into an application
user and (b) migrate pre-Firebase accounts once.
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.dependencies.auth import bearer_scheme, bearer_token, get_auth_context
from app.dependencies.database import get_db
from app.schemas.auth import (
    AuthUserResponse,
    LegacyMigrationRequest,
    LegacyMigrationResponse,
    SyncUserRequest,
)
from app.services.auth import AuthContext, AuthService

router = APIRouter()


@router.post(
    "/sync",
    response_model=AuthUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize Firebase User",
    description=(
        "Call after every Firebase sign-in/sign-up with the Firebase ID token as Bearer. "
        "Finds, links, or creates the application user for the verified identity. "
        "Idempotent; identity comes only from the token, never from the body."
    ),
)
@limiter.limit("20/minute")
def sync_user(
    request: Request,
    payload: SyncUserRequest | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    return AuthService(db).sync_user(bearer_token(credentials), payload or SyncUserRequest())


@router.post(
    "/legacy-migrate",
    response_model=LegacyMigrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Upgrade Pre-Firebase Account",
    description=(
        "One-time move of an account created before Firebase: verifies the old password, "
        "creates the Firebase user with it, and erases the stored hash. Call only after "
        "Firebase rejected an email/password sign-in."
    ),
)
@limiter.limit("5/minute")
def legacy_migrate(
    payload: LegacyMigrationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LegacyMigrationResponse:
    return AuthService(db).migrate_legacy_account(payload)


@router.get(
    "/me",
    response_model=AuthUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current Authenticated User",
    description=(
        "Profile of the signed-in user plus `email_verified`. Reachable before email "
        "verification so the app can show the verify screen; every other protected "
        "route requires it for email/password sign-ins."
    ),
)
def get_me(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    return AuthService(db).to_auth_user_response(ctx)
