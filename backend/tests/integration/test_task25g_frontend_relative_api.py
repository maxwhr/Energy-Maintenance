from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_uses_central_relative_api_prefix():
    request = (ROOT / "frontend/src/utils/request.ts").read_text(encoding="utf-8")
    system_api = (ROOT / "frontend/src/api/system.ts").read_text(encoding="utf-8")
    assert "baseURL: '/api'" in request
    assert "'/system/deployment-readiness'" in system_api
    assert "http://127.0.0.1" not in system_api

