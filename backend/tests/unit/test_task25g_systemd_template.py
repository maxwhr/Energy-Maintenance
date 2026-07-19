from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_systemd_template_uses_non_root_pure_python_uvicorn_path():
    text = (ROOT / "deploy/loongarch/config/energy-maintenance-backend.service").read_text(encoding="utf-8")
    assert "User=energy-maintenance" in text
    assert "shared/venv/bin/python -m uvicorn" in text
    assert "--reload" not in text
    assert "uv run" not in text
    assert "NoNewPrivileges=true" in text

