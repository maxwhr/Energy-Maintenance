from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from task28a_path_safety import (
    ALLOWED_PROJECT_ROOT,
    ALLOWED_SOURCE_ROOT,
    assert_project_path,
    assert_source_path,
)


CORPUS_ROOT = ALLOWED_PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1"
DEFAULT_JSON = CORPUS_ROOT / "manifests" / "source_inventory.json"
DEFAULT_CSV = CORPUS_ROOT / "manifests" / "source_inventory.csv"
DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".jp2"}
CSV_FIELDS = (
    "relative_path",
    "absolute_source_path",
    "file_name",
    "extension",
    "size_bytes",
    "modified_time",
    "sha256",
    "category",
    "suspected_duplicate_of",
    "upload_candidate",
    "readable",
    "notes",
)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extension(path: Path) -> str:
    if path.name.casefold() == ".ds_store":
        return ".DS_Store"
    return path.suffix.casefold()


def _classify(relative_path: Path, extension: str) -> tuple[str, bool, list[str]]:
    text = relative_path.as_posix().casefold()
    notes: list[str] = []
    if relative_path.name.casefold() == ".ds_store":
        return "OS_METADATA", False, ["operating-system metadata; never upload"]
    if extension in IMAGE_EXTENSIONS:
        if "逆变器检修图片" in text or relative_path.stem.casefold() in {"报错01", "报错02"}:
            return "FAULT_IMAGE", False, ["route through Media/Multimodal Case, not knowledge_documents"]
        return "UNKNOWN_REVIEW_REQUIRED", False, ["image outside the known fault-image location"]
    if extension in DOCUMENT_EXTENSIONS:
        if any(term in text for term in ("阳光电源", "sungrow", "sg 系列")):
            return "SUNGROW_FUTURE_DOCUMENT", True, ["future scope; must not enter Huawei retrieval"]
        if any(term in text for term in ("华为", "huawei", "sun2000", "fusionsolar")):
            return "HUAWEI_DOCUMENT", True, notes
        if extension in {".txt", ".md"}:
            return "CASE_NOTE", False, ["review as a case note before any knowledge upload"]
        return "UNKNOWN_REVIEW_REQUIRED", False, ["supported file type but manufacturer/scope is unclear"]
    if extension:
        return "UNSUPPORTED", False, [f"unsupported extension: {extension}"]
    return "UNKNOWN_REVIEW_REQUIRED", False, ["no extension or unrecognized file type"]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    assert_project_path(path)
    assert_project_path(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.task28a.tmp")
    assert_project_path(temporary)
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def build_inventory(source_root: Path, json_path: Path, csv_path: Path) -> dict[str, Any]:
    source_root = assert_source_path(source_root, must_exist=True)
    json_path = assert_project_path(json_path)
    csv_path = assert_project_path(csv_path)
    directories = sorted(
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_dir()
    )
    files = sorted((path for path in source_root.rglob("*") if path.is_file()), key=lambda item: item.as_posix())
    records: list[dict[str, Any]] = []
    first_path_by_hash: dict[str, str] = {}
    for file_path in files:
        safe_path = assert_source_path(file_path, must_exist=True)
        relative = safe_path.relative_to(source_root)
        extension = _extension(safe_path)
        category, upload_candidate, notes = _classify(relative, extension)
        readable = True
        try:
            digest = _hash_file(safe_path)
        except OSError as exc:
            digest = ""
            readable = False
            upload_candidate = False
            notes.append(f"read failed: {type(exc).__name__}")
        duplicate_of = first_path_by_hash.get(digest, "") if digest else ""
        if digest and not duplicate_of:
            first_path_by_hash[digest] = relative.as_posix()
        if duplicate_of:
            upload_candidate = False
            notes.append(f"byte-identical duplicate of {duplicate_of}")
        stat = safe_path.stat()
        records.append({
            "relative_path": relative.as_posix(),
            "absolute_source_path": str(safe_path),
            "file_name": safe_path.name,
            "extension": extension,
            "size_bytes": stat.st_size,
            "modified_time": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "sha256": digest,
            "category": category,
            "suspected_duplicate_of": duplicate_of,
            "upload_candidate": upload_candidate,
            "readable": readable,
            "notes": "; ".join(notes),
        })

    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source_root),
        "allowed_project_root": str(assert_project_path(ALLOWED_PROJECT_ROOT, must_exist=True)),
        "directory_count": len(directories),
        "directories": directories,
        "file_count": len(records),
        "total_bytes": sum(item["size_bytes"] for item in records),
        "readable_files": sum(bool(item["readable"]) for item in records),
        "duplicate_files": sum(bool(item["suspected_duplicate_of"]) for item in records),
        "category_counts": dict(sorted(Counter(item["category"] for item in records).items())),
        "records": records,
    }
    _atomic_json(json_path, payload)
    assert_project_path(csv_path.parent).mkdir(parents=True, exist_ok=True)
    temporary_csv = csv_path.with_name(f".{csv_path.name}.task28a.tmp")
    assert_project_path(temporary_csv)
    with temporary_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    os.replace(temporary_csv, csv_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the read-only Task 28A source inventory")
    parser.add_argument("--source-root", type=Path, default=ALLOWED_SOURCE_ROOT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    result = build_inventory(args.source_root, args.json, args.csv)
    print(json.dumps({
        "status": "inventory_created",
        "source_root": result["source_root"],
        "directory_count": result["directory_count"],
        "file_count": result["file_count"],
        "total_bytes": result["total_bytes"],
        "readable_files": result["readable_files"],
        "duplicate_files": result["duplicate_files"],
        "category_counts": result["category_counts"],
        "json": str(args.json.resolve()),
        "csv": str(args.csv.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
