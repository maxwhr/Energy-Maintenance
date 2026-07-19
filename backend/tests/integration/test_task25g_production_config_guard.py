from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_production_template_requires_real_secrets_and_disables_external_mutations():
    text = (ROOT / "deploy/loongarch/config/backend.env.example").read_text(encoding="utf-8")
    assert "SECRET_KEY=CHANGE_ME" in text
    assert "ADMIN_PASSWORD=CHANGE_ME" in text
    assert "TASK25B_ALLOW_REAL_API=false" in text
    assert "TASK25B_ALLOW_FULL_REINDEX=false" in text
    assert "VECTOR_SEARCH_ENABLED=false" in text

