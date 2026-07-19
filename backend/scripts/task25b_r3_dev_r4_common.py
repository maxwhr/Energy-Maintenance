from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r4"
R3_OUT = ROOT / ".runtime" / "task25b_r3_dev_r3"
COLLECTION = "energy_kn_te_v4_1024_v1"
RAW_PARTITION = "pilot_r2"
R3_PARTITION = "pilot_r3_semantic"
R4_PARTITION = "pilot_r4_grounded"
REPRESENTATION_VERSION = "task25b_r3_dev_r4_semantic_unit_v1"
DATASET_VERSION = "task25b_r3_dev_r4_grounded_train_dev_v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str | None) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(name: str, payload: object) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path

