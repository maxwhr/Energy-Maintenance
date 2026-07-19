import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_deployment_runtime_files_have_no_windows_paths():
    for path in (ROOT / "deploy/loongarch").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"[A-Za-z]:\\", text), path

