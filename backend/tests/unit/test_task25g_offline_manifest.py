import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_offline_manifest_rejects_foreign_wheels_and_network_installs():
    value = json.loads((ROOT / "deploy/loongarch/manifests/offline_requirements.json").read_text(encoding="utf-8"))
    assert value["network_install_allowed"] is False
    assert value["generated_wheelhouse_in_task25g"] is False
    assert "manylinux_x86_64" in value["rejected_wheel_tags"]
    assert "loongarch64" in value["allowed_wheel_tags"]

