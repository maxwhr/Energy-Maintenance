from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from task28a_path_safety import (
    ALLOWED_PROJECT_ROOT,
    ALLOWED_SOURCE_ROOT,
    assert_project_path,
    assert_source_path,
)


CORPUS_ROOT = ALLOWED_PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1"
DEFAULT_INVENTORY = CORPUS_ROOT / "manifests" / "source_inventory.json"
DEFAULT_TARGET_ROOT = CORPUS_ROOT / "raw"
DEFAULT_JOURNAL = CORPUS_ROOT / "import_reports" / "file_migration_journal.jsonl"
DEFAULT_REPORT = CORPUS_ROOT / "import_reports" / "file_migration_result.json"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative_path(value: str) -> Path:
    relative = PurePosixPath(str(value))
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"unsafe relative path: {value}")
    if ":" in relative.parts[0]:
        raise ValueError(f"drive-qualified relative path is forbidden: {value}")
    return Path(*relative.parts)


def files_match(path: Path, *, expected_size: int, expected_sha256: str) -> bool:
    return path.is_file() and path.stat().st_size == expected_size and hash_file(path) == expected_sha256


def _append_journal(path: Path, event: dict[str, Any]) -> None:
    path = assert_project_path(path)
    assert_project_path(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_report(path: Path, payload: dict[str, Any]) -> None:
    path = assert_project_path(path)
    assert_project_path(path.parent).mkdir(parents=True, exist_ok=True)
    temporary = assert_project_path(path.with_name(f".{path.name}.task28a.tmp"))
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _event(relative_path: str, status: str, **values: Any) -> dict[str, Any]:
    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "relative_path": relative_path,
        "status": status,
        **values,
    }


def migrate(
    *,
    source_root: Path,
    target_root: Path,
    inventory_path: Path,
    journal_path: Path,
    report_path: Path,
    apply: bool,
) -> dict[str, Any]:
    source_root = assert_source_path(source_root, must_exist=True)
    target_root = assert_project_path(target_root)
    inventory_path = assert_project_path(inventory_path, must_exist=True)
    journal_path = assert_project_path(journal_path)
    report_path = assert_project_path(report_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory_source = assert_source_path(inventory["source_root"], must_exist=True)
    if inventory_source != source_root:
        raise RuntimeError("inventory source root does not match the requested source root")

    results: list[dict[str, Any]] = []
    for record in inventory["records"]:
        relative_value = str(record["relative_path"])
        try:
            relative = safe_relative_path(relative_value)
            source = assert_source_path(source_root / relative)
            target = assert_project_path(target_root / relative)
            expected_size = int(record["size_bytes"])
            expected_sha256 = str(record["sha256"])
            if not expected_sha256:
                raise RuntimeError("inventory record has no SHA-256")

            source_exists = source.is_file()
            target_matches = files_match(
                target,
                expected_size=expected_size,
                expected_sha256=expected_sha256,
            ) if target.exists() else False
            if not source_exists:
                if target_matches:
                    results.append(_event(relative_value, "ALREADY_MIGRATED_VERIFIED", sha256=expected_sha256))
                else:
                    raise RuntimeError("source is missing and no verified target exists")
                continue

            if source.stat().st_size != expected_size or hash_file(source) != expected_sha256:
                raise RuntimeError("source changed after inventory")
            if not apply:
                results.append(_event(
                    relative_value,
                    "DRY_RUN_READY",
                    size_bytes=expected_size,
                    sha256=expected_sha256,
                    target_exists=target.exists(),
                    target_matches=target_matches,
                ))
                continue

            assert_project_path(target.parent).mkdir(parents=True, exist_ok=True)
            if target.exists() and not target_matches:
                raise RuntimeError("target exists with different size or SHA-256; refusing overwrite")
            if not target.exists():
                staging = assert_project_path(target.with_name(f".{target.name}.task28a-staging-{uuid4().hex}"))
                try:
                    shutil.copy2(source, staging)
                    if not files_match(staging, expected_size=expected_size, expected_sha256=expected_sha256):
                        raise RuntimeError("staging size or SHA-256 verification failed")
                    os.rename(staging, target)
                finally:
                    if staging.exists():
                        staging.unlink()
                if not files_match(target, expected_size=expected_size, expected_sha256=expected_sha256):
                    raise RuntimeError("final target size or SHA-256 verification failed")

            _append_journal(journal_path, _event(
                relative_value,
                "TARGET_VERIFIED_PENDING_SOURCE_DELETE",
                source=str(source),
                target=str(target),
                size_bytes=expected_size,
                sha256=expected_sha256,
            ))
            source.unlink()
            _append_journal(journal_path, _event(
                relative_value,
                "MOVED",
                target=str(target),
                size_bytes=expected_size,
                sha256=expected_sha256,
            ))
            results.append(_event(
                relative_value,
                "MOVED",
                target=str(target),
                size_bytes=expected_size,
                sha256=expected_sha256,
            ))
        except Exception as exc:  # noqa: BLE001 - continue safely and report each isolated failure.
            failure = _event(relative_value, "MOVE_FAILED", error_type=type(exc).__name__, error=str(exc))
            results.append(failure)
            if apply:
                _append_journal(journal_path, failure)

    moved = sum(item["status"] == "MOVED" for item in results)
    already_migrated = sum(item["status"] == "ALREADY_MIGRATED_VERIFIED" for item in results)
    failed = sum(item["status"] == "MOVE_FAILED" for item in results)
    dry_run_ready = sum(item["status"] == "DRY_RUN_READY" for item in results)
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if apply else "dry_run",
        "source_root": str(source_root),
        "target_root": str(target_root),
        "inventory_path": str(inventory_path),
        "scanned_files": len(results),
        "dry_run_ready": dry_run_ready,
        "moved_files": moved,
        "already_migrated_files": already_migrated,
        "failed_files": failed,
        "duplicate_files": int(inventory.get("duplicate_files") or 0),
        "hash_verified": failed == 0 and (dry_run_ready + moved + already_migrated == len(results)),
        "source_root_deleted": False,
        "outside_path_modified": False,
        "records": results,
    }
    _atomic_report(report_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely migrate the Task 28A corpus into the project")
    parser.add_argument("--source-root", type=Path, default=ALLOWED_SOURCE_ROOT)
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = migrate(
        source_root=args.source_root,
        target_root=args.target_root,
        inventory_path=args.inventory,
        journal_path=args.journal,
        report_path=args.report,
        apply=args.apply,
    )
    print(json.dumps({key: result[key] for key in (
        "mode",
        "scanned_files",
        "dry_run_ready",
        "moved_files",
        "already_migrated_files",
        "failed_files",
        "duplicate_files",
        "hash_verified",
        "source_root_deleted",
        "outside_path_modified",
        "target_root",
    )}, ensure_ascii=False, indent=2))
    return 1 if result["failed_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
