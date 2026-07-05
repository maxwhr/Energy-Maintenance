from __future__ import annotations

import asyncio
import http.client
import io
import json
import os
import sys
import time
from pathlib import Path
from urllib import parse

from starlette.datastructures import UploadFile

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_global_acceptance as cga  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.knowledge_service import KnowledgeService, KnowledgeServiceError  # noqa: E402


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8010").rstrip("/")
cga.API_BASE_URL = f"{BASE_URL}/api"
cga.APP_BASE_URL = BASE_URL
MARKER = f"Task24D_{time.strftime('%Y%m%d%H%M%S')}"


def record(results: list[dict], name: str, status: str, notes: str = "") -> None:
    results.append({"name": name, "status": status, "notes": notes})
    print(f"[{status}] {name}: {notes}")


def upload_document(token: str, file_name: str, content: bytes, mime: str = "text/plain") -> tuple[int, dict]:
    body, content_type = cga.multipart_body(
        [
            ("manufacturer", "huawei"),
            ("product_series", "SUN2000"),
            ("device_type", "pv_inverter"),
            ("document_type", "manual"),
            ("title", f"{MARKER} upload security"),
            ("source", "task24d_security"),
        ],
        "file",
        file_name,
        content,
        mime,
    )
    return cga.request_json("POST", "/knowledge/documents/upload", token=token, body=body, content_type=content_type)


def upload_media(token: str, file_name: str, content: bytes, mime: str = "image/png") -> tuple[int, dict]:
    body, content_type = cga.multipart_body(
        [
            ("media_type", "fault_image"),
            ("description", f"{MARKER} upload security"),
            ("manufacturer", "huawei"),
            ("product_series", "SUN2000"),
            ("device_type", "pv_inverter"),
        ],
        "file",
        file_name,
        content,
        mime,
    )
    return cga.request_json("POST", "/media/upload", token=token, body=body, content_type=content_type)


def assert_forbidden_or_error(label: str, status: int, response: dict) -> None:
    if status in {400, 401, 403, 413} or response.get("code") not in {0, 200}:
        return
    raise AssertionError(f"{label} should be rejected, got http={status}, code={response.get('code')}")


def check_json_body_limit(token: str) -> None:
    settings = get_settings()
    payload_size = settings.SECURITY_MAX_JSON_BODY_MB * 1024 * 1024 + 1024
    parsed = parse.urlparse(cga.API_BASE_URL)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, parsed.port, timeout=30)
    path = f"{parsed.path.rstrip('/')}/retrieval/query"
    try:
        conn.putrequest("POST", path)
        conn.putheader("Host", parsed.netloc)
        conn.putheader("Accept", "application/json")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Authorization", f"Bearer {token}")
        conn.putheader("Content-Length", str(payload_size))
        conn.endheaders()
        response = conn.getresponse()
        response.read()
        status = response.status
    finally:
        conn.close()
    if status != 413:
        raise AssertionError(f"large JSON body should be rejected, got http={status}")


async def check_oversize_direct() -> None:
    with SessionLocal() as db:
        service = KnowledgeService(db)
        service.settings.MAX_UPLOAD_SIZE_MB = 0
        upload = UploadFile(filename="oversize.txt", file=io.BytesIO(b"x"))
        try:
            await service._store_upload(upload, "documents")  # noqa: SLF001 - acceptance probe
        except KnowledgeServiceError:
            return
        raise AssertionError("oversize upload simulation was not rejected")


def main() -> int:
    results: list[dict] = []
    admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    viewer_user = cga.ensure_user(admin_token, f"{MARKER}_viewer", "viewer", f"{MARKER} viewer")
    viewer_token, _ = cga.login(viewer_user["username"], cga.TEST_PASSWORD)
    record(results, "auth setup", "passed", "admin/viewer ready")

    check_json_body_limit(admin_token)
    record(results, "JSON request body limit", "passed", "413 returned for oversized JSON request")

    status, response = upload_document(
        admin_token,
        "sample_task24d_pv_inverter.txt",
        "Huawei SUN2000 inverter alarm inspection sample.".encode("utf-8"),
    )
    data = cga.api_data("normal knowledge upload", status, response)
    document_id = data.get("document_id")
    if not document_id:
        raise AssertionError("normal upload did not return document_id")
    record(results, "normal upload", "passed", f"document_id={document_id}")

    status, response = upload_document(admin_token, "malware.exe", b"bad")
    assert_forbidden_or_error("unsupported extension", status, response)
    record(results, "unsupported extension rejected", "passed", f"http={status}")

    status, response = upload_document(admin_token, "../pv_inverter_manual.txt", b"path traversal sample")
    if status < 400 and response.get("code") in {0, 200}:
        original = str((response.get("data") or {}).get("original_file_name") or "")
        if ".." in original or "/" in original or "\\" in original:
            raise AssertionError("traversal filename was not sanitized")
    record(results, "traversal filename sanitized or rejected", "passed", f"http={status}")

    status, response = upload_document(admin_token, r"D:\unsafe\pv_inverter_manual.txt", b"absolute path sample")
    if status < 400 and response.get("code") in {0, 200}:
        original = str((response.get("data") or {}).get("original_file_name") or "")
        if ":" in original or "/" in original or "\\" in original:
            raise AssertionError("absolute path filename was not sanitized")
    record(results, "absolute path filename sanitized or rejected", "passed", f"http={status}")

    asyncio.run(check_oversize_direct())
    record(results, "oversize simulation rejected", "passed")

    status, response = upload_document(viewer_token, "viewer_should_fail.txt", b"viewer cannot upload")
    assert_forbidden_or_error("viewer knowledge upload", status, response)
    record(results, "viewer knowledge upload rejected", "passed", f"http={status}")

    sample_png = cga.SAMPLE_PNG
    status, response = upload_media(admin_token, "task24d_fault.png", sample_png)
    data = cga.api_data("normal media upload", status, response)
    preview_url = data.get("preview_url")
    if not preview_url:
        raise AssertionError("media upload did not return preview_url")
    data_text = json.dumps(data, ensure_ascii=False)
    if "\\" in data_text or str(ROOT_DIR) in data_text:
        raise AssertionError("media response leaked a local absolute path")
    record(results, "normal media upload", "passed", f"preview={preview_url}")

    status, response = upload_media(viewer_token, "viewer_fault.png", sample_png)
    assert_forbidden_or_error("viewer media upload", status, response)
    record(results, "viewer media upload rejected", "passed", f"http={status}")

    preview_request_url = f"{BASE_URL}{preview_url}" if str(preview_url).startswith("/api/") else str(preview_url)
    status, raw, _ = cga.request_raw(preview_request_url, token=viewer_token)
    if status not in {200, 403}:
        raise AssertionError(f"viewer preview should be readable or explicitly blocked, got {status}")
    record(results, "viewer preview auth", "passed", f"http={status}, bytes={len(raw)}")

    output = {"status": "passed", "results": results, "local_paths_in_response": False}
    runtime_dir = ROOT_DIR / ".runtime" / "security"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "upload_security_result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "checks": len(results)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
