from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25b_r2_u2"
INBOX = BACKEND / "storage" / "formal_corpus_inbox" / "huawei_official"
RUNTIME.mkdir(parents=True, exist_ok=True)
INBOX.mkdir(parents=True, exist_ok=True)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

OFFICIAL_DOMAINS = {
    "solar.huawei.com", "info.support.huawei.com", "support.huawei.com",
    "digitalpower.huawei.com", "fusionsolar.huawei.com", "intl.fusionsolar.huawei.com",
    "huawei.com", "www.huawei.com",
}
OFFICIAL_CDN_DOMAINS = {"download.huawei.com", "support-download.huawei.com"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_official_url(url: str, *, allow_cdn: bool = True) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = OFFICIAL_DOMAINS | (OFFICIAL_CDN_DOMAINS if allow_cdn else set())
    return parsed.scheme == "https" and any(host == item or host.endswith("." + item) for item in allowed)


def sanitize(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(term in lowered for term in ("api_key", "authorization", "cookie", "token", "password", "secret")):
        return "[REDACTED]"
    if lowered in {"content", "document_text", "vector", "vectors"}:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: sanitize(item, name) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item, key) for item in value]
    return value


def write_json(name: str, payload: Any) -> Path:
    path = RUNTIME / name
    path.write_text(json.dumps(sanitize(payload), ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(path), "sha256": sha256_file(path)}, ensure_ascii=False))
    return path


def write_csv(name: str, fields: list[str], rows: Iterable[dict[str, Any]]) -> Path:
    path = RUNTIME / name
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _cell(sanitize(row.get(field), field)) for field in fields})
    return path


def _cell(value: Any) -> Any:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value
