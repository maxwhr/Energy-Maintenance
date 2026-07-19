from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
DEPLOY = ROOT / "deploy" / "loongarch"
RUNTIME = ROOT / ".runtime" / "task25g"
RUNTIME.mkdir(parents=True, exist_ok=True)

EXPECTED_ALEMBIC_REVISION = "20260712_0015"
EXPECTED_MACHINE = "loongarch64"
SUPPORTED_OS_FAMILY = "kylin"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_manifest(path: Path, *, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if path.is_dir():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            relative = item.relative_to(path).as_posix()
            if any(relative == value or relative.startswith(f"{value}/") for value in exclude):
                continue
            files.append({
                "path": relative,
                "size": item.stat().st_size,
                "sha256": sha256_file(item),
            })
    return {
        "root": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name,
        "file_count": len(files),
        "total_bytes": sum(int(item["size"]) for item in files),
        "files": files,
        "aggregate_sha256": sha256_value(files),
    }


def read_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    if not target.is_file():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: str | Path, payload: Any, *, overwrite: bool = True) -> Path:
    target = Path(path)
    if not target.is_absolute():
        output_root = Path(os.environ.get("TASK25G_WRITE_OUTPUT_DIR", RUNTIME))
        target = output_root / target
    if target.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite frozen Task 25G evidence: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def run(command: list[str], *, cwd: Path = ROOT, timeout: int = 300, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return {
            "command": command,
            "exit_code": 127,
            "stdout": "",
            "stderr": "command not found",
        }
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def platform_facts() -> dict[str, Any]:
    machine = platform.machine().lower()
    system = platform.system().lower()
    return {
        "system": system,
        "machine": machine,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "is_windows_development_host": os.name == "nt",
        "is_loongarch64": machine == EXPECTED_MACHINE,
        "is_linux": system == "linux",
        "real_machine_acceptance": "PENDING",
    }


def public_path(path: Path) -> str:
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT).as_posix()
    return path.name
