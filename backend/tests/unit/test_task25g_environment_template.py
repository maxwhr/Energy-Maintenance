from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_environment_template_is_placeholder_only_and_safe_by_default():
    text = (ROOT / "deploy/loongarch/config/backend.env.example").read_text(encoding="utf-8")
    assert "CHANGE_ME" in text
    assert "APP_ENV=production" in text
    assert "TASK25B_ALLOW_FULL_REINDEX=false" in text
    assert "EXTERNAL_REAL_CALLS_ENABLED=false" in text
    assert "D:\\" not in text

