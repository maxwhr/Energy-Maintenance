from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.system import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserCreateRequest, UserUpdateRequest


ALLOWED_ROLES = {"admin", "expert", "engineer", "viewer"}
ALLOWED_STATUSES = {"active", "disabled"}


class UserServiceError(ValueError):
    pass


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def get_user(self, user_id: UUID) -> User | None:
        return self.repository.get_by_id(user_id)

    def create_user(self, payload: UserCreateRequest) -> User:
        self._validate_role(payload.role)
        self._validate_status(payload.status)
        if self.repository.get_by_username(payload.username):
            raise UserServiceError("Username already exists")
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            role=payload.role,
            status=payload.status,
            is_active=payload.status == "active",
        )
        user = self.repository.create(user)
        self.db.commit()
        return user

    def list_users(
        self,
        *,
        role: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        if role:
            self._validate_role(role)
        if status:
            self._validate_status(status)
        if page < 1:
            raise UserServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise UserServiceError("page_size must be between 1 and 100")
        users, total = self.repository.list_users(
            role=role,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": users,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def update_user(self, user_id: UUID, payload: UserUpdateRequest) -> User:
        user = self.repository.get_by_id(user_id)
        if not user:
            raise UserServiceError("User not found")
        if payload.role is not None:
            self._validate_role(payload.role)
            user.role = payload.role
        if payload.status is not None:
            self._validate_status(payload.status)
            user.status = payload.status
            user.is_active = payload.status == "active"
        if payload.display_name is not None:
            user.display_name = payload.display_name
        if payload.password:
            user.password_hash = hash_password(payload.password)
        user = self.repository.update(user)
        self.db.commit()
        return user

    def disable_user(self, user_id: UUID) -> User:
        user = self.repository.get_by_id(user_id)
        if not user:
            raise UserServiceError("User not found")
        user.status = "disabled"
        user.is_active = False
        user = self.repository.update(user)
        self.db.commit()
        return user

    def enable_user(self, user_id: UUID) -> User:
        user = self.repository.get_by_id(user_id)
        if not user:
            raise UserServiceError("User not found")
        user.status = "active"
        user.is_active = True
        user = self.repository.update(user)
        self.db.commit()
        return user

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in ALLOWED_ROLES:
            raise UserServiceError("Invalid role")

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in ALLOWED_STATUSES:
            raise UserServiceError("Invalid status")
