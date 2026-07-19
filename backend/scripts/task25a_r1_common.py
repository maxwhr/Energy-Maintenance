from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25a_r1"
RUNTIME.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path | str) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path | str) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_paths(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((p for p in paths if p.is_file()), key=lambda p: rel(p)):
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        file_hash = sha256_file(path)
        if file_hash:
            digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def write_json(path: Path | str, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_json(path: Path | str, default: Any = None) -> Any:
    path = Path(path)
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path | str, rows: list[dict[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})
    return path


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def run(command: list[str], cwd: Path = ROOT, timeout: int = 120) -> dict[str, Any]:
    started = now_iso()
    begin = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )
        return {
            "command": command,
            "started_at": started,
            "completed_at": now_iso(),
            "duration_seconds": round((datetime.now(timezone.utc) - begin).total_seconds(), 3),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "started_at": started,
            "completed_at": now_iso(),
            "duration_seconds": round((datetime.now(timezone.utc) - begin).total_seconds(), 3),
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": "command timed out",
        }
    except OSError as exc:
        return {
            "command": command,
            "started_at": started,
            "completed_at": now_iso(),
            "duration_seconds": round((datetime.now(timezone.utc) - begin).total_seconds(), 3),
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: command unavailable",
        }


def environment_label() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cwd": rel(Path.cwd()),
        "api_base_url": os.getenv("TASK25A_R1_BASE_URL", "http://127.0.0.1:8010"),
        "database_host": "127.0.0.1",
        "database_port": 55432,
        "external_provider_mode": "disabled_for_task25a_r1",
    }


def artifact_hashes(paths: Iterable[Path | str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in paths:
        path = Path(item)
        digest = sha256_file(path)
        if digest:
            result[rel(path)] = digest
    return result


def register_test(entry: dict[str, Any]) -> None:
    path = RUNTIME / "test_execution_registry.json"
    payload = read_json(path, {"generated_at": now_iso(), "tests": []})
    tests = payload.setdefault("tests", [])
    entry = {
        "test_id": entry["test_id"],
        "name": entry.get("name", entry["test_id"]),
        "category": entry.get("category", "audit"),
        "command": entry.get("command", ""),
        "started_at": entry.get("started_at", now_iso()),
        "completed_at": entry.get("completed_at", now_iso()),
        "duration_seconds": entry.get("duration_seconds", 0.0),
        "environment": entry.get("environment", environment_label()),
        "api_base_url": entry.get("api_base_url", os.getenv("TASK25A_R1_BASE_URL", "http://127.0.0.1:8010")),
        "database_host": entry.get("database_host", "127.0.0.1"),
        "database_port": entry.get("database_port", 55432),
        "real_external_api_used": bool(entry.get("real_external_api_used", False)),
        "mocked": bool(entry.get("mocked", False)),
        "exit_code": entry.get("exit_code", 0),
        "status": entry.get("status", "PASSED"),
        "assertion_count": int(entry.get("assertion_count", 0)),
        "passed_assertions": int(entry.get("passed_assertions", 0)),
        "failed_assertions": int(entry.get("failed_assertions", 0)),
        "artifact_paths": [rel(Path(p)) for p in entry.get("artifact_paths", [])],
        "artifact_hashes": artifact_hashes(entry.get("artifact_paths", [])),
        "notes": entry.get("notes", ""),
    }
    tests = [item for item in tests if item.get("test_id") != entry["test_id"]]
    tests.append(entry)
    payload["generated_at"] = now_iso()
    payload["tests"] = sorted(tests, key=lambda item: item["test_id"])
    write_json(path, payload)
