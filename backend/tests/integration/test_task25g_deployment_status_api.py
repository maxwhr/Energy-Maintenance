from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.main import app


def test_deployment_readiness_is_sanitized_and_windows_stays_pending():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="admin")
    try:
        response = TestClient(app).get("/api/system/deployment-readiness")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["docker_required"] is False
    assert data["deployment_mode"] == "native_systemd_nginx_postgresql"
    assert data["real_machine_acceptance"]["status"] == "PENDING"
    serialized = str(data)
    assert "D:\\" not in serialized
    assert "DATABASE_URL" not in serialized
    assert "SECRET_KEY" not in serialized


def test_ordinary_user_receives_summary_without_risk_items():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="viewer")
    try:
        response = TestClient(app).get("/api/system/deployment-readiness")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    assert "items" not in response.json()["data"]["native_dependency_risks"]

