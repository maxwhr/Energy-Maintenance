from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_rollback_uses_atomic_current_symlink_switch():
    text = (ROOT / "deploy/loongarch/scripts/rollback_release.sh").read_text(encoding="utf-8")
    assert "ln -sfn" in text
    assert "mv -Tf" in text
    assert "${EM_CURRENT_LINK}" in text

