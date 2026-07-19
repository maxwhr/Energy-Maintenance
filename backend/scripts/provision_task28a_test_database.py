from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from task28a_path_safety import assert_project_path  # noqa: E402


TEST_ROLE = "energy_maintenance_test_user"
TEST_DATABASE = "energy_maintenance_task27a_test"
ADMIN_ENV_KEY = "TASK28A_PG_ADMIN_URL"
LOCAL_ENV_PATH = PROJECT_ROOT / ".env.task27a.test.local"
DEFAULT_SQL_PATH = PROJECT_ROOT / ".runtime" / "task28a" / "create_test_database.sql"
SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
FORBIDDEN_DATABASES = {"energy_maintenance", "postgres", "template0", "template1"}


def assert_test_identifiers(role_name: str, database_name: str) -> tuple[str, str]:
    role = role_name.strip().casefold()
    database = database_name.strip().casefold()
    if role != TEST_ROLE or database != TEST_DATABASE:
        raise ValueError("Task 28A may provision only the designated test role and database")
    if not SAFE_IDENTIFIER.fullmatch(role) or not SAFE_IDENTIFIER.fullmatch(database):
        raise ValueError("unsafe PostgreSQL identifier")
    if database in FORBIDDEN_DATABASES or not any(token in database for token in ("_test", "task27a", "task28a")):
        raise ValueError("target is not an isolated test database")
    return role, database


def write_manual_sql(path: Path) -> None:
    target = assert_project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f"""-- Task 28A administrator action. Replace the placeholder interactively.
-- Run against the native PostgreSQL instance on port 55432.
CREATE ROLE {TEST_ROLE}
WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
PASSWORD '<SECURE_RANDOM_PASSWORD>';

CREATE DATABASE {TEST_DATABASE}
WITH OWNER = {TEST_ROLE} ENCODING = 'UTF8' TEMPLATE = template0;

SELECT datname, pg_catalog.pg_get_userbyid(datdba) AS owner
FROM pg_database
WHERE datname = '{TEST_DATABASE}';
"""
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, target)


def _connect_admin(admin_url_value: str) -> psycopg.Connection:
    parsed = make_url(admin_url_value)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("administrator URL must use PostgreSQL")
    return psycopg.connect(
        host=parsed.host,
        port=parsed.port,
        dbname=parsed.database or "postgres",
        user=parsed.username,
        password=parsed.password,
        autocommit=True,
        connect_timeout=10,
    )


def _write_local_environment(admin_url_value: str, password: str) -> None:
    parsed = make_url(admin_url_value)
    host = parsed.host or "127.0.0.1"
    port = parsed.port or 5432
    encoded_password = quote(password, safe="")
    content = (
        f"DATABASE_URL=postgresql+psycopg://{TEST_ROLE}:{encoded_password}@{host}:{port}/{TEST_DATABASE}\n"
        "APP_ENV=test\n"
        "ALLOW_REAL_EXTERNAL_API=false\n"
        "TASK28A_ALLOW_REAL_PROVIDER=false\n"
    )
    target = assert_project_path(LOCAL_ENV_PATH)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, target)


def provision(admin_url_value: str) -> dict[str, object]:
    role, database = assert_test_identifiers(TEST_ROLE, TEST_DATABASE)
    password = secrets.token_urlsafe(32)
    result: dict[str, object] = {
        "status": "BLOCKED",
        "role": role,
        "database": database,
        "role_created": False,
        "role_password_rotated": False,
        "database_created": False,
        "database_owner_verified": False,
        "local_environment_written": False,
        "secrets_printed": False,
    }

    with _connect_admin(admin_url_value) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
            current_user, is_superuser, can_create_db, can_create_role = cursor.fetchone()
            result["administrator_role"] = current_user
            if not is_superuser and not (can_create_db and can_create_role):
                result["status"] = "BLOCKED_ADMIN_ROLE_LACKS_PRIVILEGES"
                return result

            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
                "FROM pg_roles WHERE rolname = %s",
                (role,),
            )
            existing_role = cursor.fetchone()
            if existing_role and any(existing_role):
                result["status"] = "BLOCKED_EXISTING_TEST_ROLE_IS_OVERPRIVILEGED"
                return result
            if existing_role:
                cursor.execute(
                    sql.SQL(
                        "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(password)),
                )
                result["role_password_rotated"] = True
            else:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(password)),
                )
                result["role_created"] = True

            cursor.execute(
                "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (database,),
            )
            existing_database = cursor.fetchone()
            if existing_database and existing_database[0] != role:
                result["status"] = "BLOCKED_EXISTING_DATABASE_OWNER_MISMATCH"
                return result
            if not existing_database:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} WITH OWNER = {} ENCODING = 'UTF8' TEMPLATE = template0").format(
                        sql.Identifier(database),
                        sql.Identifier(role),
                    )
                )
                result["database_created"] = True

            cursor.execute(
                "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (database,),
            )
            owner_row = cursor.fetchone()
            result["database_owner_verified"] = bool(owner_row and owner_row[0] == role)
            if not result["database_owner_verified"]:
                result["status"] = "BLOCKED_DATABASE_OWNER_VERIFICATION_FAILED"
                return result

    _write_local_environment(admin_url_value, password)
    result["local_environment_written"] = True
    result["status"] = "PROVISIONED"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision only the isolated Task 28A PostgreSQL role/database")
    parser.add_argument("--apply", action="store_true", help=f"requires {ADMIN_ENV_KEY}")
    parser.add_argument("--sql-output", type=Path, default=DEFAULT_SQL_PATH)
    args = parser.parse_args()

    assert_test_identifiers(TEST_ROLE, TEST_DATABASE)
    write_manual_sql(args.sql_output)
    admin_url_value = os.getenv(ADMIN_ENV_KEY, "").strip()
    if not args.apply:
        print(json.dumps({
            "status": "DRY_RUN",
            "role": TEST_ROLE,
            "database": TEST_DATABASE,
            "admin_url_present": bool(admin_url_value),
            "manual_sql_path": str(assert_project_path(args.sql_output)),
            "secrets_printed": False,
        }, ensure_ascii=False, indent=2))
        return 0
    if not admin_url_value:
        print(json.dumps({
            "status": "BLOCKED_ADMIN_ACTION_REQUIRED",
            "reason": f"{ADMIN_ENV_KEY} is not configured",
            "manual_sql_path": str(assert_project_path(args.sql_output)),
            "secrets_printed": False,
        }, ensure_ascii=False, indent=2))
        return 2

    result = provision(admin_url_value)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PROVISIONED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
