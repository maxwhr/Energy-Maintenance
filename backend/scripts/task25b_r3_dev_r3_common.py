from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r3"
R2_OUT = ROOT / ".runtime" / "task25b_r3_dev_r2"
R2_DATASET = "task25b_r3_dev_r2_zh_v3"
SEMANTIC_PARTITION = "pilot_r3_semantic"
SEMANTIC_VERSION = "task25b_r3_dev_r3_semantic_v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_hash(value: str | None) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def normalized(value: str | None) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())


def terms(value: str | None) -> set[str]:
    text = normalized(value)
    if not text:
        return set()
    latin = set(re.findall(r"[a-z]+\d*[a-z\d-]*", (value or "").lower()))
    han = {text[index:index + width] for width in (2, 3) for index in range(max(0, len(text) - width + 1))}
    return {item for item in {*latin, *han} if len(item) >= 2}


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def masked_preview(value: str | None, *, limit: int = 56) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit - 1]}…"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(name: str, payload: object) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path
