from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25d"
TASK = "Task 25D"
TASK25C_STATUS = "MULTIMODAL_BENCHMARK_INSUFFICIENT"
R6_STATUS = "DEFERRED_QWEN3_RERANK_CONFIG"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path_or_name: str | Path) -> dict[str, Any]:
    path = Path(path_or_name)
    if not path.is_absolute():
        path = OUT / path
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, payload: Any, *, immutable: bool = False) -> Path:
    output_root = Path(os.environ.get("TASK25D_WRITE_OUTPUT_DIR", OUT))
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / name
    if immutable and path.exists():
        raise SystemExit(f"immutable Task 25D artifact already exists: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
