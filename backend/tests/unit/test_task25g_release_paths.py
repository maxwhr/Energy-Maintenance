import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_release_paths_are_native_linux_paths():
    value = json.loads((ROOT / "deploy/loongarch/manifests/runtime_files.json").read_text(encoding="utf-8"))
    assert value["release_root"].startswith("/opt/energy-maintenance/releases/")
    assert value["current_symlink"] == "/opt/energy-maintenance/current"
    assert value["environment_file"] == "/etc/energy-maintenance/backend.env"

