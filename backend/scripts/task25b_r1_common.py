from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25b_r1"
RUNTIME.mkdir(parents=True, exist_ok=True)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitize(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(term in lowered for term in ("api_key", "authorization", "secret", "password")):
        return "[REDACTED]"
    if lowered in {"raw_vector", "query_vector", "embedding_vector"}:
        return "[REDACTED]"
    if lowered in {"vector", "vectors"} and isinstance(value, list) and (
        len(value) > 32 or (value and isinstance(value[0], list))
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: sanitize(item, name) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item, key) for item in value]
    return value


def write_json(name: str, payload: dict[str, Any]) -> Path:
    path = RUNTIME / name
    safe = sanitize(payload)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(path), "sha256": sha256_file(path)}, ensure_ascii=False))
    return path


def write_csv(name: str, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> Path:
    path = RUNTIME / name
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(sanitize(row.get(key), key)) for key in fieldnames})
    print(json.dumps({"artifact": str(path), "sha256": sha256_file(path)}, ensure_ascii=False))
    return path


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value
