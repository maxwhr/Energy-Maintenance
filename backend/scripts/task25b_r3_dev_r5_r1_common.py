from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r1"
COLLECTION = "energy_kn_te_v4_1024_v1"
RAW_PARTITION = "pilot_r2"
R3_PARTITION = "pilot_r3_semantic"
R4_PARTITION = "pilot_r4_grounded"
R5_PARTITION = "pilot_r5_query_aware"
TRAIN_DEV_VERSION = "task25b_r3_dev_r5_r1_train_dev_v2"
FORMAL_VERSION = "task25b_r3_dev_r5_r1_zh_v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(name: str, payload: object) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path

