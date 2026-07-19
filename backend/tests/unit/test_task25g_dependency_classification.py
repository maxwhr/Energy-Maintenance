import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_all_native_dependencies_are_classified():
    value = json.loads((ROOT / "deploy/loongarch/manifests/python_dependencies.json").read_text(encoding="utf-8"))
    rows = [row for row in value["dependencies"] if row["native_extension"] or row["system_library"]]
    assert rows
    assert all(row["loongarch_risk"] != "UNKNOWN" for row in rows)
    assert all(row["action"] for row in rows)

