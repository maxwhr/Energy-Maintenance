from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck_contract_uses_unified_response():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "success"
    assert isinstance(body["data"], dict)

