from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.system import User
from app.repositories.user_repository import UserRepository


def main() -> int:
    username = os.getenv("ADMIN_USERNAME", "admin")
    environment = (os.getenv("APP_ENV") or os.getenv("ENV") or "development").strip().lower()
    configured_password = os.getenv("ADMIN_PASSWORD")
    if not configured_password and environment == "production":
        print(
            "ERROR: ADMIN_PASSWORD is required when APP_ENV or ENV is production.",
            file=sys.stderr,
        )
        return 2
    if configured_password:
        password = configured_password
    else:
        password = "admin123456"
        print(
            "WARNING: ADMIN_PASSWORD is not set. Using the local-development password "
            "'admin123456'. Set ADMIN_PASSWORD before any shared or production deployment.",
            file=sys.stderr,
        )
    display_name = os.getenv("ADMIN_DISPLAY_NAME", "System Administrator")

    db = SessionLocal()
    try:
        repository = UserRepository(db)
        existing_user = repository.get_by_username(username)
        if existing_user:
            changed = False
            if not existing_user.password_hash:
                existing_user.password_hash = hash_password(password)
                changed = True
            if existing_user.role != "admin":
                existing_user.role = "admin"
                changed = True
            if existing_user.status != "active":
                existing_user.status = "active"
                changed = True
            if not existing_user.is_active:
                existing_user.is_active = True
                changed = True
            if changed:
                db.commit()
                print(f"Admin user repaired: {username}")
                return 0
            print(f"Admin user already exists: {username}")
            return 0

        admin_user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role="admin",
            status="active",
            is_active=True,
        )
        repository.create(admin_user)
        db.commit()
        print(f"Admin user created: {username}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
