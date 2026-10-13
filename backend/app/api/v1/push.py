"""Push token registration for the signed-in user's device."""

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.services import push

router = APIRouter()


class PushTokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=255, pattern=r"^(Expo|Exponent)PushToken\[.+\]$")
    platform: str | None = Field(default=None, max_length=16)


@router.post("", status_code=status.HTTP_204_NO_CONTENT, summary="Register a device push token")
def register(
    body: PushTokenRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    push.register_token(db, current_user.id, body.token, body.platform)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a device push token")
def unregister(
    body: PushTokenRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    push.unregister_token(db, current_user.id, body.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
