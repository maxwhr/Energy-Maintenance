from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import TokenError, TokenExpiredError, decode_access_token
from app.models.system import User
from app.repositories.user_repository import UserRepository


bearer_scheme = HTTPBearer(auto_error=False)


def api_exception(status_code: int, code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "data": None,
        },
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise api_exception(status.HTTP_401_UNAUTHORIZED, 40101, "Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(str(payload["sub"]))
    except TokenExpiredError as exc:
        raise api_exception(status.HTTP_401_UNAUTHORIZED, 40102, "Token expired") from exc
    except (TokenError, ValueError, KeyError) as exc:
        raise api_exception(status.HTTP_401_UNAUTHORIZED, 40103, "Invalid token") from exc
    user = UserRepository(db).get_by_id(user_id)
    if not user:
        raise api_exception(status.HTTP_401_UNAUTHORIZED, 40104, "Current user not found")
    if user.status != "active" or not user.is_active:
        raise api_exception(status.HTTP_403_FORBIDDEN, 40301, "Account is disabled")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise api_exception(status.HTTP_403_FORBIDDEN, 40302, "Permission denied")
        return current_user

    return dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise api_exception(status.HTTP_403_FORBIDDEN, 40302, "Permission denied")
    return current_user
