import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / ".runtime" / "task25f_r1"


def artifact(name: str):
    path = RUNTIME / name
    assert path.is_file(), f"missing Task 25F-R1 artifact: {name}"
    return json.loads(path.read_text(encoding="utf-8"))
