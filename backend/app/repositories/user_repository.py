from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.system import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.db.scalar(statement)

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def list_users(
        self,
        *,
        role: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        filters = []
        if role:
            filters.append(User.role == role)
        if status:
            filters.append(User.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))

        count_statement = select(func.count()).select_from(User)
        list_statement = select(User).order_by(User.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        users = list(
            self.db.scalars(
                list_statement.offset((page - 1) * page_size).limit(page_size)
            )
        )
        return users, total

    def update(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user
