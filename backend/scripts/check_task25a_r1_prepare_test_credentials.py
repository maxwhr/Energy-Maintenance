from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.core.security import hash_password
from app.core.database import SessionLocal
from app.models.system import User
from task25a_r1_common import RUNTIME


PRIVATE_FILE = RUNTIME / ".test_credentials.private.json"


def prepare() -> None:
    password = secrets.token_urlsafe(36)
    users = {
        "admin": ("Task25AR1_admin", "admin"),
        "expert": ("Task25AR1_expert", "expert"),
        "engineer": ("Task25AR1_engineer", "engineer"),
        "viewer": ("Task25AR1_viewer", "viewer"),
    }
    with SessionLocal() as session:
        for label, (username, role) in users.items():
            user = session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(username=username, display_name=f"Task25AR1 {label}", role=role, status="active")
                session.add(user)
            user.password_hash = hash_password(password)
            user.display_name = f"Task25AR1 {label}"
            user.role = role
            user.status = "active"
        session.commit()
    payload = {label: {"username": data[0], "password": password} for label, data in users.items()}
    PRIVATE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(PRIVATE_FILE, 0o600)
    except OSError:
        pass
    print("credentials_ready=true")


def cleanup() -> None:
    if PRIVATE_FILE.exists():
        PRIVATE_FILE.unlink()
    print("credentials_removed=true")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    cleanup() if args.cleanup else prepare()
