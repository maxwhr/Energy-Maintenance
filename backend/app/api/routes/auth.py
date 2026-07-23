from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import BusinessException
from app.models.system import User
from app.schemas.auth import AuthUserRead, LoginRequest, LoginResponse
from app.schemas.common import success_response
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user, token, expires_in = AuthService(db).authenticate(payload.username, payload.password)
    except AuthServiceError as exc:
        raise BusinessException(
            message=str(exc),
            business_code=40100,
            http_status=401,
        ) from exc
    data = LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=AuthUserRead.model_validate(user),
    ).model_dump(mode="json")
    return success_response(data)


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return success_response(
        AuthUserRead.model_validate(current_user).model_dump(mode="json")
    )


@router.post("/logout")
def logout() -> dict:
    return success_response()
