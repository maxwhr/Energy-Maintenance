from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_rollback_never_downgrades_or_deletes_database():
    text = (ROOT / "deploy/loongarch/scripts/rollback_release.sh").read_text(encoding="utf-8").lower()
    assert "alembic downgrade" not in text
    assert "drop database" not in text
    assert "rm -rf" not in text

