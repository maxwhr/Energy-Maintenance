from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.system import User
from app.repositories.user_repository import UserRepository


class AuthServiceError(ValueError):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def authenticate(self, username: str, password: str) -> tuple[User, str, int]:
        user = self.repository.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            raise AuthServiceError("Invalid username or password")
        if user.status != "active" or not user.is_active:
            raise AuthServiceError("Account is disabled")
        token, expires_in = create_access_token(str(user.id))
        user.last_login_at = datetime.now(timezone.utc)
        self.repository.update(user)
        self.db.commit()
        return user, token, expires_in
