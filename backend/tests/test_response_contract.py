from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.exceptions import BusinessException, unhandled_exception_handler
from app.core.security import create_access_token
from app.main import app


ROUTES_DIR = Path(__file__).resolve().parents[1] / "app" / "api" / "routes"


@pytest.fixture
def api_client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def auth_headers(user) -> dict[str, str]:
    token, _ = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def assert_error_contract(response, *, status: int, code: int) -> None:
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["data"] is None
    assert response.json()["message"]


def test_login_success_uses_http_200_and_code_zero(
    api_client,
    make_user,
) -> None:
    user = make_user(username="contract_login_user", role="admin")
    response = api_client.post(
        "/api/auth/login",
        json={"username": user.username, "password": "LocalOnly!234"},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["message"] == "success"
    assert response.json()["data"]["user"]["username"] == user.username


def test_login_failure_uses_http_401_and_business_code(api_client) -> None:
    response = api_client.post(
        "/api/auth/login",
        json={"username": "missing-user", "password": "wrong-password"},
    )
    assert_error_contract(response, status=401, code=40100)


def test_protected_route_without_token_uses_http_401(api_client) -> None:
    response = api_client.get("/api/users")
    assert_error_contract(response, status=401, code=40101)


def test_permission_denied_uses_http_403_without_auth_failure(
    api_client,
    make_user,
) -> None:
    viewer = make_user(username="contract_viewer", role="viewer")
    response = api_client.get(
        "/api/users",
        headers=auth_headers(viewer),
    )
    assert_error_contract(response, status=403, code=40302)


def test_missing_user_uses_http_404(
    api_client,
    admin_user,
) -> None:
    response = api_client.get(
        f"/api/users/{uuid4()}",
        headers=auth_headers(admin_user),
    )
    assert_error_contract(response, status=404, code=40401)


def test_duplicate_user_uses_http_409_and_creation_uses_201(
    api_client,
    admin_user,
) -> None:
    payload = {
        "username": "contract_duplicate",
        "password": "StrongLocal!234",
        "display_name": "Contract User",
        "role": "viewer",
        "status": "active",
    }
    first = api_client.post(
        "/api/users",
        json=payload,
        headers=auth_headers(admin_user),
    )
    assert first.status_code == 201
    assert first.json()["code"] == 0

    duplicate = api_client.post(
        "/api/users",
        json=payload,
        headers=auth_headers(admin_user),
    )
    assert_error_contract(duplicate, status=409, code=40001)


def test_business_parameter_error_uses_http_400(
    api_client,
    admin_user,
) -> None:
    response = api_client.get(
        "/api/users?role=unsupported",
        headers=auth_headers(admin_user),
    )
    assert_error_contract(response, status=400, code=40002)


def test_request_validation_uses_http_422_and_null_data(api_client) -> None:
    response = api_client.post("/api/auth/login", json={})
    assert_error_contract(response, status=422, code=42200)
    assert "validation" in response.json()["message"].casefold()


def test_oversized_json_request_uses_http_413(api_client) -> None:
    response = api_client.post(
        "/api/auth/login",
        content=b"x" * (6 * 1024 * 1024),
        headers={"content-type": "application/json"},
    )
    assert_error_contract(response, status=413, code=41300)


def test_unhandled_exception_uses_safe_http_500_response() -> None:
    isolated_app = FastAPI()
    isolated_app.add_exception_handler(Exception, unhandled_exception_handler)

    @isolated_app.get("/boom")
    def boom():
        raise RuntimeError(
            "SELECT password_hash FROM users at C:\\private\\server.py"
        )

    with TestClient(
        isolated_app,
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/boom")
    assert_error_contract(response, status=500, code=50000)
    rendered = response.text.casefold()
    assert "select" not in rendered
    assert "password_hash" not in rendered
    assert "server.py" not in rendered


@pytest.mark.parametrize(
    "message",
    [
        "device_code already exists",
        "Invalid case status transition: draft -> completed",
    ],
)
def test_duplicate_and_state_conflicts_map_to_http_409(message: str) -> None:
    error = BusinessException.from_service_error(
        RuntimeError(message),
        business_code=40001,
    )
    assert error.http_status == 409


def test_route_sources_use_only_the_shared_response_contract() -> None:
    success_code_pattern = re.compile(
        r"[\"']code[\"']\s*:\s*200\b"
    )
    local_helper_pattern = re.compile(r"def\s+(ok|fail)\s*\(")
    for path in ROUTES_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not success_code_pattern.search(source), path
        assert not local_helper_pattern.search(source), path
        assert "error_response(" not in source, path
