from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
TASK25F_RUNTIME = ROOT / ".runtime" / "task25f"
RUNTIME = ROOT / ".runtime" / "task25f_r1"
RUNTIME.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    if not target.is_file():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any, *, overwrite: bool = True) -> Path:
    target = Path(path)
    if not target.is_absolute():
        output_root = Path(os.environ.get("TASK25F_R1_WRITE_OUTPUT_DIR", RUNTIME))
        target = output_root / target
    if target.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite immutable Task 25F-R1 evidence: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def write_jsonl(path: str | Path, rows: list[dict[str, Any]], *, overwrite: bool = True) -> Path:
    target = Path(path)
    if not target.is_absolute():
        output_root = Path(os.environ.get("TASK25F_R1_WRITE_OUTPUT_DIR", RUNTIME))
        target = output_root / target
    if target.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite immutable Task 25F-R1 evidence: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")
    return target


def write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> Path:
    target = Path(path)
    if not target.is_absolute():
        output_root = Path(os.environ.get("TASK25F_R1_WRITE_OUTPUT_DIR", RUNTIME))
        target = output_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)
    return target


def run(command: list[str], *, cwd: Path = ROOT, timeout: int = 300) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def safe_settings_snapshot() -> dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings()
    names = (
        "RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL",
        "RAG_QUERY_UNDERSTANDING_SCHEMA_VERSION",
        "RAG_QUERY_WEIGHT_ORIGINAL",
        "RAG_QUERY_WEIGHT_CANONICAL",
        "RAG_QUERY_WEIGHT_INTENT",
        "RAG_QUERY_WEIGHT_CONDITION",
        "RAG_DETERMINISTIC_RERANK_ENABLED",
        "DETERMINISTIC_RERANK_WEIGHTS_VERSION",
        "RAG_DEDICATED_RERANK_ENABLED",
        "RAG_DEDICATED_RERANK_PROVIDER",
        "RAG_DEDICATED_RERANK_MODEL",
        "RAG_OPTIONAL_LLM_TIEBREAK_ENABLED",
        "RAG_MAX_QUERY_VARIANT_CONCURRENCY",
        "RAG_MAX_VECTOR_CONCURRENCY",
        "RAG_SCOPE_BATCH_HYDRATION_ENABLED",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIM",
        "EMBEDDING_QUERY_CACHE_TTL_SECONDS",
        "EMBEDDING_QUERY_CACHE_MAX_ENTRIES",
        "DASHVECTOR_PHYSICAL_COLLECTION",
        "DASHVECTOR_TIMEOUT_SECONDS",
        "VECTOR_SEARCH_ENABLED",
        "TASK25B_ALLOW_REAL_API",
        "TASK25B_ALLOW_FULL_REINDEX",
    )
    return {name: getattr(settings, name, None) for name in names}


def git_lines(*args: str) -> list[str]:
    result = run(["git", *args])
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or f"git {' '.join(args)} failed")
    return result["stdout"].splitlines() if result["stdout"] else []
