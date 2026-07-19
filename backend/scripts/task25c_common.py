from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25c"
TASK = "Task 25C"
BENCHMARK_VERSION = "task25c_multimodal_engineering_benchmark_v1"
DEFERRED_RERANK_STATUS = "DEFERRED_QWEN3_RERANK_CONFIG"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path_or_name: str | Path) -> dict[str, Any]:
    path = Path(path_or_name)
    if not path.is_absolute():
        path = OUT / path
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, payload: Any, *, immutable: bool = False) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if immutable and path.exists():
        raise SystemExit(f"immutable Task 25C artifact already exists: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
