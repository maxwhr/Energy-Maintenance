from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r6"
SOURCE = ROOT / ".runtime" / "task25b_r3_dev_r5_r5"
DATASET_VERSION = "task25b_r3_dev_r5_r6_train_dev_v1"
FORMAL_VERSION = "task25b_r3_dev_r5_r6_zh_v1"
RERANK_PROVIDER = "dashscope"
RERANK_MODEL = "qwen3-rerank"
INSTRUCT_VERSION = "task25b_r3_dev_r5_r6_instruct_v1"
INSTRUCT = (
    "Given an equipment maintenance troubleshooting query, rank passages that directly answer the user's "
    "requested information. Prefer specific, source-grounded causes, actions, procedures, prerequisites, "
    "safety requirements, and verification steps over generic background or merely topically related text. "
    "Penalize passages with mismatched device models, alarm codes, components, or occurrence conditions."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


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
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if immutable and path.exists():
        raise SystemExit(f"immutable task artifact already exists: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def p95(values: list[float]) -> float:
    ordered = sorted(float(value) for value in values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3) if ordered else 0.0


def ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 6) if denominator else 0.0
