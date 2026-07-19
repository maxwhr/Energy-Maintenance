from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25g_r2"
TASK25G_RUNTIME = ROOT / ".runtime" / "task25g"
TASK25G_R1_RUNTIME = ROOT / ".runtime" / "task25g_r1"
TASK25G_REPORT = ROOT / "docs" / "25G_loongarch_kylin_and_knowledge_graph_readiness_report.md"
TASK25G_R1_REPORT = ROOT / "docs" / "25G_R1_knowledge_graph_grounding_remediation_report.md"
TASK25G_R2_REPORT = ROOT / "docs" / "25G_R2_current_chinese_knowledge_graph_grounding_report.md"
EXPECTED_ALEMBIC_REVISION = "20260712_0015"
MATCHER_VERSION = "task25g_r2_current_chinese_matcher_v1"
RELATION_MATRIX_VERSION = "task25g_r2_relation_evidence_matrix_v1"
CORE_MANIFEST_VERSION = "task25g_r2_production_core_fact_manifest_v1"


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


def sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def public_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def directory_manifest(path: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if path.is_dir():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            files.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "size": item.stat().st_size,
                    "sha256": sha256_file(item),
                }
            )
    return {
        "root": public_path(path),
        "file_count": len(files),
        "total_bytes": sum(int(item["size"]) for item in files),
        "files": files,
        "aggregate_sha256": sha256_value(files),
    }


def read_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    if not target.is_file():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: str | Path, payload: Any, *, overwrite: bool = True) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    if target.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite frozen Task 25G-R2 evidence: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return target


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )
    return target


def run(command: list[str], *, cwd: Path = ROOT, timeout: int = 300) -> dict[str, Any]:
    try:
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
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "command": command,
            "exit_code": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "stdout": "",
            "stderr": exc.__class__.__name__,
        }
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def alembic_state() -> dict[str, Any]:
    heads = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], cwd=BACKEND)
    current = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], cwd=BACKEND)
    return {
        "heads_exit_code": heads["exit_code"],
        "heads": heads["stdout"],
        "current_exit_code": current["exit_code"],
        "current": current["stdout"],
    }


def git_snapshot() -> dict[str, Any]:
    status = run(["git", "status", "--short"])
    staged = run(["git", "diff", "--cached", "--name-only"])
    status_lines = status["stdout"].splitlines() if status["stdout"] else []
    return {
        "status_exit_code": status["exit_code"],
        "status_lines": status_lines,
        "status_sha256": sha256_value(status_lines),
        "staged_files": staged["stdout"].splitlines() if staged["stdout"] else [],
    }


def zip_inventory() -> list[dict[str, Any]]:
    return [
        {"path": public_path(path), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(ROOT.rglob("*.zip"))
        if ".git" not in path.parts
    ]


def vector_namespace_counts(session: Any) -> list[dict[str, Any]]:
    from sqlalchemy import text

    return [
        {"namespace": str(row[0]), "count": int(row[1])}
        for row in session.execute(
            text(
                "SELECT namespace, count(*) FROM knowledge_chunk_vector_indexes "
                "GROUP BY namespace ORDER BY namespace"
            )
        )
    ]
