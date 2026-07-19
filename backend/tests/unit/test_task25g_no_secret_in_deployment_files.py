import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_deployment_files_contain_no_embedded_database_password():
    for path in (ROOT / "deploy/loongarch").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            matches = re.findall(r"postgresql(?:\+psycopg)?://[^:\s]+:([^@\s]+)@", text)
            assert all(value.startswith("CHANGE_ME") for value in matches), path

