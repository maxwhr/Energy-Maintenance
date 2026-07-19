from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import engine as application_engine  # noqa: E402


DEFAULT_DATABASE = "energy_maintenance_task27a_test"
DEFAULT_OWNER = "energy_user"
FORBIDDEN_DATABASES = {"energy_maintenance", "postgres", "template0", "template1"}
SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


def assert_safe_test_database_name(name: str) -> str:
    normalized = name.strip().casefold()
    if normalized in FORBIDDEN_DATABASES:
        raise ValueError("target database is explicitly forbidden")
    if "_test" not in normalized and "task27a" not in normalized:
        raise ValueError("target database name must contain _test or task27a")
    if not SAFE_IDENTIFIER.fullmatch(normalized):
        raise ValueError("target database name contains unsafe characters")
    return normalized


def assert_safe_role_name(name: str) -> str:
    normalized = name.strip().casefold()
    if not SAFE_IDENTIFIER.fullmatch(normalized):
        raise ValueError("owner role name contains unsafe characters")
    return normalized


def build_create_database_sql(database_name: str, owner: str) -> str:
    database_name = assert_safe_test_database_name(database_name)
    owner = assert_safe_role_name(owner)
    return (
        f'CREATE DATABASE "{database_name}" OWNER "{owner}" '
        "ENCODING 'UTF8' TEMPLATE template0;"
    )


def _database_exists(connection, database_name: str) -> bool:
    return bool(connection.scalar(
        text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
        {"database_name": database_name},
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely provision an isolated Task 27A PostgreSQL database")
    parser.add_argument("--target-database", default=DEFAULT_DATABASE)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--apply", action="store_true", help="Requires TASK27A_ADMIN_DATABASE_URL")
    args = parser.parse_args()

    try:
        target = assert_safe_test_database_name(args.target_database)
        owner = assert_safe_role_name(args.owner)
    except ValueError as exc:
        parser.error(str(exc))
    create_sql = build_create_database_sql(target, owner)
    admin_url_value = os.getenv("TASK27A_ADMIN_DATABASE_URL", "").strip()

    result = {
        "mode": "apply" if args.apply else "dry_run",
        "target_database": target,
        "owner": owner,
        "admin_url_present": bool(admin_url_value),
        "application_database": application_engine.url.database,
        "manual_create_sql": create_sql,
        "database_created": False,
        "existing_database_deleted": False,
        "secrets_printed": False,
    }

    if not args.apply:
        result["status"] = "DRY_RUN_ADMIN_ACTION_REQUIRED"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not admin_url_value:
        result["status"] = "BLOCKED_ADMIN_ACTION_REQUIRED"
        result["reason"] = "TASK27A_ADMIN_DATABASE_URL is not configured"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    admin_url = make_url(admin_url_value)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            role = connection.execute(text(
                "SELECT current_user, (SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user)",
            )).one()
            result["admin_role"] = role[0]
            result["admin_can_create_database"] = bool(role[1])
            if not role[1]:
                result["status"] = "BLOCKED_ADMIN_ROLE_LACKS_CREATEDB"
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
            if not connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :owner"), {"owner": owner}):
                result["status"] = "BLOCKED_OWNER_ROLE_MISSING"
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
            if _database_exists(connection, target):
                result["status"] = "EXISTS_MANUAL_REVIEW_REQUIRED"
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
            connection.execute(text(create_sql))
            if not _database_exists(connection, target):
                result["status"] = "CREATE_VERIFICATION_FAILED"
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2
            result["database_created"] = True
            result["status"] = "CREATED"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    finally:
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
