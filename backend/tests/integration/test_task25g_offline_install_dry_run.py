import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_offline_install_is_no_index_and_does_not_build_frontend():
    backend = (ROOT / "deploy/loongarch/scripts/install_backend.sh").read_text(encoding="utf-8")
    frontend = (ROOT / "deploy/loongarch/scripts/install_frontend.sh").read_text(encoding="utf-8")
    assert "--no-index" in backend
    assert "--find-links" in backend
    assert "parse_dry_run" in backend
    assert not re.search(r"\bnpm\s+(?:install|run|build)\b", frontend)
    assert not re.search(r"(?:^|\s)node(?:\s|$)", frontend, re.MULTILINE)
    assert "index.html" in frontend
