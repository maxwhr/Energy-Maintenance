from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from task25b_r2_u2_common import BACKEND, INBOX, RUNTIME, now_iso, is_official_url, write_csv, write_json

USER_AGENT = "Energy-Maintenance-Huawei-Official-Corpus/1.0 (+official-public-documents; no-auth)"
MAX_BYTES = 100 * 1024 * 1024


def safe_name(title: str, url: str, extension: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._")[:100]
    if not value:
        value = "huawei_document"
    suffix = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{value}_{suffix}.{extension}"


def valid_magic(path: Path, extension: str) -> bool:
    head = path.read_bytes()[:8]
    return head.startswith(b"%PDF-") if extension == "pdf" else head.startswith(b"PK\x03\x04")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-only", action="store_true")
    parser.add_argument("--respect-access-control", action="store_true")
    parser.add_argument("--max-files", type=int, default=100)
    args = parser.parse_args()
    if not (args.official_only and args.respect_access_control):
        raise SystemExit("--official-only and --respect-access-control are required")
    max_files = max(1, min(100, args.max_files))
    discovery = json.loads((RUNTIME / "huawei_discovery.json").read_text(encoding="utf-8"))
    records = [item for item in discovery.get("records", []) if item.get("download_available") and item.get("official_domain")]
    client = httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        timeout=90, follow_redirects=True, limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    manifest = []
    failures = []
    hashes: dict[str, str] = {}
    for existing in INBOX.glob("*.*"):
        if existing.is_file() and existing.suffix.lower() in {".pdf", ".docx"}:
            hashes[hashlib.sha256(existing.read_bytes()).hexdigest()] = existing.name
    downloaded = duplicates = total_size = 0
    last_request = 0.0
    for item in records[:max_files]:
        source_url = item["source_url"]
        if not is_official_url(source_url):
            failures.append({"source_url": source_url, "reason": "not_official"})
            continue
        delay = 1.0 - (time.monotonic() - last_request)
        if delay > 0:
            time.sleep(delay)
        temp = INBOX / (safe_name(item.get("document_title") or "document", source_url, item["file_type"]) + ".part")
        try:
            with client.stream("GET", source_url) as response:
                last_request = time.monotonic()
                final_url = str(response.url)
                if response.status_code in {401, 403}:
                    failures.append({"source_url": source_url, "final_url": final_url, "reason": "BLOCKED_ACCESS", "http_status": response.status_code})
                    continue
                response.raise_for_status()
                if not is_official_url(final_url):
                    failures.append({"source_url": source_url, "final_url": final_url, "reason": "redirected_outside_official_domains"})
                    continue
                mime = response.headers.get("content-type", "").split(";")[0].lower()
                extension = "pdf" if "pdf" in mime or item["file_type"] == "pdf" else (
                    "docx" if "wordprocessingml" in mime or item["file_type"] == "docx" else ""
                )
                if not extension:
                    failures.append({"source_url": source_url, "final_url": final_url, "reason": "unsupported_mime", "mime": mime})
                    continue
                declared = int(response.headers.get("content-length") or 0)
                if declared > MAX_BYTES:
                    failures.append({"source_url": source_url, "final_url": final_url, "reason": "file_too_large", "declared_size": declared})
                    continue
                digest = hashlib.sha256()
                size = 0
                with temp.open("wb") as handle:
                    for block in response.iter_bytes(1024 * 1024):
                        size += len(block)
                        if size > MAX_BYTES:
                            raise ValueError("file_too_large")
                        digest.update(block)
                        handle.write(block)
                sha = digest.hexdigest()
                if not valid_magic(temp, extension):
                    temp.unlink(missing_ok=True)
                    failures.append({"source_url": source_url, "final_url": final_url, "reason": "invalid_file_header", "mime": mime})
                    continue
                if sha in hashes:
                    temp.unlink(missing_ok=True)
                    duplicates += 1
                    duplicate_of = hashes[sha]
                    status = "DUPLICATE"
                    relative = f"storage/formal_corpus_inbox/huawei_official/{duplicate_of}"
                else:
                    filename = safe_name(item.get("document_title") or "document", final_url, extension)
                    target = INBOX / filename
                    if target.exists():
                        target = INBOX / f"{target.stem}_{sha[:8]}{target.suffix}"
                    temp.replace(target)
                    hashes[sha] = target.name
                    downloaded += 1
                    total_size += size
                    status = "DOWNLOADED"
                    relative = f"storage/formal_corpus_inbox/huawei_official/{target.name}"
                manifest.append({
                    "status": status, "source_provenance": "VENDOR_OFFICIAL", "manufacturer": "Huawei",
                    "issuer": "Huawei Technologies Co., Ltd.", "rights_basis": "vendor_public",
                    "source_url": source_url, "source_page_url": item.get("source_page"), "final_url": final_url,
                    "downloaded_at": now_iso(), "file_sha256": sha, "file_size": size,
                    "relative_file_path": relative, "document_version": item.get("version"),
                    "language": item.get("language"), "product_family": item.get("product_family"),
                    "device_models": item.get("device_models") or [], "document_title": item.get("document_title"),
                    "document_type": item.get("document_type"), "file_type": extension,
                    "redistribution_authorized": False,
                })
        except Exception as exc:
            temp.unlink(missing_ok=True)
            failures.append({"source_url": source_url, "reason": str(exc)[:120] if isinstance(exc, ValueError) else type(exc).__name__})

    fields = [
        "status", "source_provenance", "manufacturer", "issuer", "rights_basis", "source_url",
        "source_page_url", "final_url", "downloaded_at", "file_sha256", "file_size", "relative_file_path",
        "document_version", "language", "product_family", "device_models", "document_title", "document_type",
        "file_type", "redistribution_authorized",
    ]
    result = {
        "generated_at": now_iso(), "downloaded": downloaded,
        "pdf": sum(item["file_type"] == "pdf" and item["status"] == "DOWNLOADED" for item in manifest),
        "docx": sum(item["file_type"] == "docx" and item["status"] == "DOWNLOADED" for item in manifest),
        "duplicate": duplicates, "failed": len(failures), "total_size": total_size,
        "sha256_complete": all(bool(item.get("file_sha256")) for item in manifest),
        "access_control_bypassed": False, "cookies_used": False, "authorization_used": False,
        "manifest": manifest,
    }
    write_json("huawei_download_result.json", result)
    write_json("huawei_download_failures.json", {"generated_at": now_iso(), "failures": failures})
    write_csv("huawei_document_manifest.csv", fields, manifest)
    print(json.dumps({key: result[key] for key in ("downloaded", "pdf", "docx", "duplicate", "failed", "total_size", "sha256_complete")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
