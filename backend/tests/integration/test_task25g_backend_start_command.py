from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_backend_start_command_needs_no_uv_or_native_uvicorn_extras():
    text = (ROOT / "deploy/loongarch/config/energy-maintenance-backend.service").read_text(encoding="utf-8")
    start = next(line for line in text.splitlines() if line.startswith("ExecStart="))
    assert "/shared/venv/bin/python -m uvicorn app.main:app" in start
    assert " uv " not in start
    assert "uvloop" not in start
    assert "httptools" not in start

