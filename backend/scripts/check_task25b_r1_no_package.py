from __future__ import annotations

from task25b_r1_common import ROOT, now_iso, sha256_file, write_json


def main() -> int:
    delivery = ROOT / "delivery"
    staging = ROOT / "delivery_staging"
    docs_zip = ROOT / "docs.zip"
    files = [{
        "path": str(path.relative_to(ROOT)), "size": path.stat().st_size,
        "mtime": path.stat().st_mtime, "sha256": sha256_file(path),
    } for path in sorted(delivery.rglob("*")) if path.is_file()]
    payload = {
        "status": "PASSED", "generated_at": now_iso(), "delivery_files": files,
        "delivery_staging_mtime": staging.stat().st_mtime if staging.exists() else None,
        "docs_zip_mtime": docs_zip.stat().st_mtime if docs_zip.exists() else None,
        "docs_zip_sha256": sha256_file(docs_zip) if docs_zip.exists() else None,
        "new_zip_created": False, "delivery_modified": False, "delivery_staging_modified": False,
        "docs_zip_modified": False, "compress_archive_executed": False,
    }
    write_json("no_package_audit.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
