import json
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[3]


def test_all_declared_runtime_paths_are_absolute_posix_paths():
    value = json.loads((ROOT / "deploy/loongarch/manifests/runtime_files.json").read_text(encoding="utf-8"))
    paths = [value["current_symlink"], value["shared_venv"], value["environment_file"], *value["writable_directories"]]
    assert all(PurePosixPath(path).is_absolute() for path in paths)
    assert all("\\" not in path for path in paths)

