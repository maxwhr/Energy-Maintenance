from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_release_rollback_dry_run_has_no_database_or_recursive_delete_action():
    text = (ROOT / "deploy/loongarch/scripts/rollback_release.sh").read_text(encoding="utf-8")
    assert "parse_dry_run" in text
    assert "alembic" not in text.lower()
    assert "pg_" not in text.lower()
    assert "rm -rf" not in text.lower()
    assert "database downgrade was not executed" in text

