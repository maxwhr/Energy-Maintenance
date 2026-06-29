from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.system import User
from app.schemas.auth import AuthUserRead, LoginRequest, LoginResponse
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["auth"])


def ok(data: object | None = None, message: str = "success") -> dict:
    return {
        "code": 0,
        "message": message,
        "data": {} if data is None else data,
    }


def fail(message: str, code: int = 400) -> dict:
    return {
        "code": code,
        "message": message,
        "data": None,
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user, token, expires_in = AuthService(db).authenticate(payload.username, payload.password)
    except AuthServiceError as exc:
        return fail(str(exc), 40100)
    data = LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=AuthUserRead.model_validate(user),
    ).model_dump(mode="json")
    return ok(data)


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return ok(AuthUserRead.model_validate(current_user).model_dump(mode="json"))


@router.post("/logout")
def logout() -> dict:
    return ok()
