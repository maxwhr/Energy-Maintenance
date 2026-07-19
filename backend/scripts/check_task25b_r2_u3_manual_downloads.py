from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from sqlalchemy import select

from task25b_r2_u3_common import MANUAL_DOWNLOAD, RUNTIME, is_official_url, now_iso, sha256_file, write_csv, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeDocument


FIELDS = [
    "filename", "source_url", "source_page_url", "title", "product_family", "device_models",
    "document_type", "document_version", "release_date", "language", "rights_basis", "notes",
]


def file_signature_ok(path: Path) -> bool:
    header = path.read_bytes()[:8]
    return (path.suffix.lower() == ".pdf" and header.startswith(b"%PDF-")) or (
        path.suffix.lower() == ".docx" and header.startswith(b"PK\x03\x04")
    )


def main() -> int:
    manifest_path = MANUAL_DOWNLOAD / "manual_manifest.csv"
    rows = list(csv.DictReader(manifest_path.open(encoding="utf-8-sig"))) if manifest_path.exists() else []
    with SessionLocal() as db:
        database_hashes = {
            str((item.metadata_json or {}).get("file_sha256"))
            for item in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_type == "vendor_official"))
            if (item.metadata_json or {}).get("file_sha256")
        }
    u2_manifest_path = RUNTIME.parent / "task25b_r2_u2" / "huawei_document_manifest.csv"
    u2_hashes = set()
    if u2_manifest_path.exists():
        u2_hashes = {row.get("file_sha256") for row in csv.DictReader(u2_manifest_path.open(encoding="utf-8-sig"))}
    results = []
    seen_hashes = set()
    for row in rows:
        path = MANUAL_DOWNLOAD / Path(row.get("filename") or "").name
        status = "READY_FOR_QUALITY_CHECK"
        digest = None
        if not row.get("source_url"):
            status = "UNKNOWN_SOURCE"
        elif not is_official_url(row["source_url"]):
            status = "UNKNOWN_SOURCE"
        elif not path.exists() or not path.is_file():
            status = "MISSING_FILE"
        elif path.suffix.lower() not in {".pdf", ".docx"} or not file_signature_ok(path):
            status = "INVALID_FILE"
        else:
            digest = sha256_file(path)
            if digest in database_hashes or digest in u2_hashes or digest in seen_hashes:
                status = "DUPLICATE"
            seen_hashes.add(digest)
        models = [item.strip() for item in re.split(r"[;,|]", row.get("device_models") or "") if item.strip()]
        results.append({**row, "file_sha256": digest, "status": status, "device_models": models, "checked_at": now_iso()})
    payload = {
        "generated_at": now_iso(), "manifest_present": manifest_path.exists(), "manifest_rows": len(rows),
        "ready": sum(item["status"] == "READY_FOR_QUALITY_CHECK" for item in results),
        "unknown_source": sum(item["status"] == "UNKNOWN_SOURCE" for item in results),
        "duplicate": sum(item["status"] == "DUPLICATE" for item in results),
        "invalid_or_missing": sum(item["status"] in {"INVALID_FILE", "MISSING_FILE"} for item in results),
        "automatic_approval": False, "records": results,
    }
    write_json("manual_download_check.json", payload)
    write_csv("manual_download_check.csv", FIELDS + ["file_sha256", "status", "checked_at"], results)
    print(json.dumps({k: payload[k] for k in ("manifest_present", "manifest_rows", "ready", "unknown_source", "duplicate", "invalid_or_missing")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
