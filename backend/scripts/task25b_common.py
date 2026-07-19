from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25b"
RUNTIME.mkdir(parents=True, exist_ok=True)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_result(name: str, payload: dict[str, Any]) -> Path:
    path = RUNTIME / name
    safe = _sanitize(payload)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(safe, ensure_ascii=False, indent=2, default=str))
    return path


def _sanitize(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(term in lowered for term in ("api_key", "authorization", "secret", "password")):
        return "[REDACTED]"
    if lowered in {"vector", "vectors", "raw_vector", "query_vector", "embedding_vector"}:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: _sanitize(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, key) for item in value]
    return value


def real_gate(settings, cli_allowed: bool) -> tuple[bool, list[str]]:
    reasons = []
    if not cli_allowed:
        reasons.append("--allow-real-api is required")
    if not settings.TASK25B_ALLOW_REAL_API:
        reasons.append("TASK25B_ALLOW_REAL_API=false")
    if not settings.EMBEDDING_REAL_CALL_ENABLED:
        reasons.append("EMBEDDING_REAL_CALL_ENABLED=false")
    if not settings.DASHVECTOR_REAL_CALL_ENABLED:
        reasons.append("DASHVECTOR_REAL_CALL_ENABLED=false")
    return not reasons, reasons
