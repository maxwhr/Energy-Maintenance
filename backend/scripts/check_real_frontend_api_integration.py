from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_global_acceptance as cga  # noqa: E402


API_BASE_URL = os.getenv("REAL_FRONTEND_API_BASE_URL") or os.getenv(
    "GLOBAL_ACCEPTANCE_API_BASE_URL",
    "http://127.0.0.1:8000/api",
)
API_BASE_URL = API_BASE_URL.rstrip("/")
APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
RUN_ID = os.getenv("REAL_FRONTEND_API_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task21A_{RUN_ID}"
RESULT_PATH = ROOT_DIR / ".runtime" / "21A_real_api_integration_result.json"

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = APP_BASE_URL
cga.ADMIN_USERNAME = os.getenv("REAL_FRONTEND_API_ADMIN_USERNAME") or os.getenv(
    "GLOBAL_ACCEPTANCE_ADMIN_USERNAME",
    os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin"),
)
cga.ADMIN_PASSWORD = os.getenv("REAL_FRONTEND_API_ADMIN_PASSWORD") or os.getenv(
    "GLOBAL_ACCEPTANCE_ADMIN_PASSWORD",
    os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456"),
)
cga.TEST_PASSWORD = os.getenv("REAL_FRONTEND_API_TEST_PASSWORD", "Task21A_pass123")
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class IntegrationError(AssertionError):
    pass


@dataclass(slots=True)
class FrontendApiCall:
    file: str
    function: str
    method: str
    raw_path: str
    normalized_path: str
    line: int
    matched_backend_path: str | None = None


@dataclass(slots=True)
class IntegrationScan:
    frontend_pages: list[str] = field(default_factory=list)
    frontend_api_calls: list[FrontendApiCall] = field(default_factory=list)
    matched_calls: list[FrontendApiCall] = field(default_factory=list)
    missing_calls: list[FrontendApiCall] = field(default_factory=list)
    backend_paths: dict[str, set[str]] = field(default_factory=dict)
    old_api_hits: list[dict[str, Any]] = field(default_factory=list)
    fake_hits: list[dict[str, Any]] = field(default_factory=list)
    page_api_matrix: list[dict[str, Any]] = field(default_factory=list)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def fetch_openapi_paths() -> dict[str, set[str]]:
    openapi_url = f"{APP_BASE_URL}/openapi.json"
    try:
        with request.urlopen(openapi_url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise IntegrationError(f"OpenAPI fetch failed: http={exc.code}, body={body[:300]}") from exc
    except Exception as exc:  # noqa: BLE001
        raise IntegrationError(f"OpenAPI fetch failed: {exc}") from exc
    title = str(payload.get("info", {}).get("title", ""))
    if "Energy-Maintenance" not in title:
        raise IntegrationError(f"OpenAPI title is not Energy-Maintenance: {title!r}")
    paths: dict[str, set[str]] = {}
    for path, methods in (payload.get("paths") or {}).items():
        paths[str(path)] = {method.upper() for method in methods if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}}
    return paths


def normalize_frontend_path(path: str) -> str:
    normalized = path.strip()
    normalized = re.sub(r"\$\{[^}]+\}", "{param}", normalized)
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    if normalized.startswith("/api/"):
        return normalized
    if normalized.startswith("/"):
        return f"/api{normalized}"
    return f"/api/{normalized}"


def path_matches(frontend_path: str, backend_path: str) -> bool:
    front_segments = frontend_path.strip("/").split("/")
    back_segments = backend_path.strip("/").split("/")
    if len(front_segments) != len(back_segments):
        return False
    for front, back in zip(front_segments, back_segments):
        if front == back:
            continue
        if front.startswith("{") and front.endswith("}"):
            continue
        if back.startswith("{") and back.endswith("}"):
            continue
        return False
    return True


def match_backend_path(call: FrontendApiCall, backend_paths: dict[str, set[str]]) -> str | None:
    for backend_path, methods in backend_paths.items():
        if call.method.upper() in methods and path_matches(call.normalized_path, backend_path):
            return backend_path
    return None


def nearest_exported_function(text: str, index: int) -> str:
    prefix = text[:index]
    matches = list(re.finditer(r"export\s+const\s+([A-Za-z0-9_]+)\s*=", prefix))
    if matches:
        return matches[-1].group(1)
    return "<inline>"


def scan_frontend_api_calls(backend_paths: dict[str, set[str]]) -> IntegrationScan:
    scan = IntegrationScan(backend_paths=backend_paths)
    api_dir = ROOT_DIR / "frontend" / "src" / "api"
    views_dir = ROOT_DIR / "frontend" / "src" / "views"

    scan.frontend_pages = [
        str(path.relative_to(ROOT_DIR)).replace("\\", "/")
        for path in sorted(views_dir.rglob("*.vue"))
    ]

    call_pattern = re.compile(
        r"request\.(?P<method>get|post|put|delete|patch)\s*(?:<[^>]*>)?\s*\(\s*(?P<quote>['\"`])(?P<path>[^'\"`]+)(?P=quote)",
        re.MULTILINE,
    )
    for path in sorted(api_dir.glob("*.ts")):
        text = read_text(path)
        relative = str(path.relative_to(ROOT_DIR)).replace("\\", "/")
        for match in call_pattern.finditer(text):
            raw_path = match.group("path")
            normalized = normalize_frontend_path(raw_path)
            line = text[: match.start()].count("\n") + 1
            call = FrontendApiCall(
                file=relative,
                function=nearest_exported_function(text, match.start()),
                method=match.group("method").upper(),
                raw_path=raw_path,
                normalized_path=normalized,
                line=line,
            )
            call.matched_backend_path = match_backend_path(call, backend_paths)
            scan.frontend_api_calls.append(call)
            if call.matched_backend_path:
                scan.matched_calls.append(call)
            else:
                scan.missing_calls.append(call)

    build_page_api_matrix(scan)
    scan.old_api_hits = scan_for_patterns(
        [
            (ROOT_DIR / "frontend" / "src", r"/api/v1|/api/records/qa|/workorders\b|/api/workorders\b"),
            (ROOT_DIR / "README.md", r"/api/v1|/api/records/qa|/api/workorders\b"),
            (ROOT_DIR / "backend" / "README.md", r"/api/v1|/api/records/qa|/api/workorders\b"),
            (ROOT_DIR / "docs", r"/api/v1|/api/records/qa|/api/workorders\b"),
        ]
    )
    scan.fake_hits = scan_for_patterns(
        [
            (
                ROOT_DIR / "frontend" / "src",
                r"Promise\.resolve|mockData|fakeSuccess|fake success|假成功|伪造成功",
            ),
            (
                ROOT_DIR / "backend" / "app",
                r"Promise\.resolve|mockData|fakeSuccess|fake success|假成功|伪造成功",
            ),
        ]
    )
    return scan


def scan_for_patterns(targets: list[tuple[Path, str]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    ignored_parts = {"node_modules", "dist", ".venv", "__pycache__", "static", ".git"}
    for root, pattern in targets:
        if not root.exists():
            continue
        files: list[Path]
        if root.is_file():
            files = [root]
        else:
            files = [
                path
                for path in root.rglob("*")
                if path.is_file()
                and not any(part in ignored_parts for part in path.parts)
                and path.suffix.lower() in {".ts", ".vue", ".js", ".py", ".md", ".json"}
            ]
        compiled = re.compile(pattern, re.IGNORECASE)
        for path in files:
            text = read_text(path)
            for line_no, line in enumerate(text.splitlines(), 1):
                if compiled.search(line):
                    hits.append(
                        {
                            "file": str(path.relative_to(ROOT_DIR)).replace("\\", "/"),
                            "line": line_no,
                            "text": line.strip()[:240],
                        }
                    )
    return hits


def build_page_api_matrix(scan: IntegrationScan) -> None:
    api_functions = {call.function: call for call in scan.frontend_api_calls if call.function != "<inline>"}
    views_dir = ROOT_DIR / "frontend" / "src" / "views"
    for path in sorted(views_dir.rglob("*.vue")):
        text = read_text(path)
        used_calls = [
            {
                "function": name,
                "method": call.method,
                "path": call.normalized_path,
                "matched_backend_path": call.matched_backend_path,
            }
            for name, call in sorted(api_functions.items())
            if re.search(rf"\b{name}\s*\(", text)
        ]
        scan.page_api_matrix.append(
            {
                "page": str(path.relative_to(ROOT_DIR)).replace("\\", "/"),
                "api_functions": used_calls,
                "connected": all(item["matched_backend_path"] for item in used_calls),
            }
        )


def check_static_scan(recorder: cga.Recorder, scan_holder: dict[str, Any]) -> None:
    backend_paths = fetch_openapi_paths()
    scan = scan_frontend_api_calls(backend_paths)
    scan_holder["scan"] = scan
    if scan.missing_calls:
        missing = "; ".join(
            f"{call.file}:{call.line} {call.method} {call.normalized_path}"
            for call in scan.missing_calls[:10]
        )
        raise IntegrationError(f"frontend API calls missing backend OpenAPI match: {missing}")
    old_frontend_hits = [hit for hit in scan.old_api_hits if hit["file"].startswith("frontend/src/")]
    if old_frontend_hits:
        old = "; ".join(f"{hit['file']}:{hit['line']}" for hit in old_frontend_hits[:10])
        raise IntegrationError(f"old frontend API references found: {old}")
    if scan.fake_hits:
        fake = "; ".join(f"{hit['file']}:{hit['line']}" for hit in scan.fake_hits[:10])
        raise IntegrationError(f"mock/fake success markers found in source: {fake}")
    recorder.add(
        "frontend/backend integration",
        "static API path matrix",
        "passed",
        f"pages={len(scan.frontend_pages)}, api_calls={len(scan.frontend_api_calls)}, matched={len(scan.matched_calls)}",
    )


def check_backend_identity(recorder: cga.Recorder) -> None:
    status, response = cga.request_json("GET", "/health")
    data = cga.require_dict(cga.api_data("health", status, response), "health")
    if data.get("name") != "Energy-Maintenance":
        raise IntegrationError(f"unexpected health name: {data.get('name')}")
    recorder.add("backend identity", "health", "passed", f"name={data.get('name')}")
    status, response = cga.request_json("GET", "/system/status")
    data = cga.require_dict(cga.api_data("system status", status, response), "system status")
    if data.get("database_status") != "online":
        raise IntegrationError(f"database_status is {data.get('database_status')!r}, expected online")
    recorder.add("backend identity", "database status", "passed", "database_status=online")


def setup_task21a_auth(state: cga.AcceptanceState, recorder: cga.Recorder) -> None:
    token, admin_user = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    state.admin_token = token
    state.users["admin"] = admin_user
    recorder.add("auth/RBAC", "admin login", "passed", f"user={admin_user.get('username')}")

    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        user = cga.ensure_user(token, username, role, f"{MARKER} {role}")
        state.users[role] = user
        role_token, _ = cga.login(username, cga.TEST_PASSWORD)
        setattr(state, f"{role}_token", role_token)
        recorder.add("auth/RBAC", f"{role} account ready", "passed", f"id={user.get('id')}")

    for label, token_value in (
        ("admin", state.admin_token),
        ("expert", state.expert_token),
        ("engineer", state.engineer_token),
        ("viewer", state.viewer_token),
    ):
        status, response = cga.request_json("GET", "/auth/me", token=token_value)
        user = cga.api_data(f"auth/me {label}", status, response)
        if not isinstance(user, dict) or not user.get("username"):
            raise IntegrationError(f"auth/me {label} returned invalid user")
        recorder.add("auth/RBAC", f"auth/me {label}", "passed", f"role={user.get('role')}")


def check_direct_document_upload(state: cga.AcceptanceState, recorder: cga.Recorder, holder: dict[str, Any]) -> None:
    unique_phrase = f"{MARKER} 华为 SUN2000 逆变器绝缘告警真实上传闭环短语"
    file_text = (
        "# SUN2000 insulation alarm checklist\n\n"
        f"{unique_phrase}\n"
        "When the Huawei SUN2000 PV inverter reports low insulation resistance, verify DC isolation, "
        "string cable moisture, connector damage, cabinet grounding, and alarm reset conditions. "
        "Before opening the inverter cabinet, isolate AC and DC sources and follow lockout rules.\n"
    )
    fields = [
        ("title", f"{MARKER} direct upload SUN2000 insulation checklist"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
        ("document_type", "manual"),
        ("source", f"{MARKER}_direct_upload"),
        ("description", "Task 21A direct upload verification document."),
    ]
    body, content_type = cga.multipart_body(
        fields,
        "file",
        f"{MARKER}_sun2000_upload.md",
        file_text.encode("utf-8"),
        "text/markdown",
    )
    status, response = cga.request_json(
        "POST",
        "/knowledge/documents/upload",
        token=state.engineer_token,
        body=body,
        content_type=content_type,
        timeout=90,
    )
    upload = cga.require_dict(cga.api_data("direct document upload", status, response), "direct document upload")
    document_id = str(upload.get("document_id") or "")
    chunk_count = int(upload.get("chunk_count") or 0)
    if not document_id or upload.get("parse_status") != "parsed" or chunk_count <= 0:
        raise IntegrationError(f"document upload did not parse into chunks: {upload}")
    holder["document_id"] = document_id
    holder["unique_phrase"] = unique_phrase
    holder["chunk_count"] = chunk_count
    recorder.add(
        "knowledge upload",
        "upload and parse",
        "passed",
        f"document_id={document_id}, chunk_count={chunk_count}",
    )

    status, response = cga.request_json(
        "GET",
        f"/knowledge/documents?{cga.encode_query({'keyword': MARKER, 'page': 1, 'page_size': 10})}",
        token=state.viewer_token,
    )
    page = cga.require_page(cga.api_data("list direct document", status, response), "list direct document")
    if not any(str(item.get("id") or item.get("document_id")) == document_id for item in page["items"]):
        raise IntegrationError("uploaded document was not visible in document list")
    recorder.add("knowledge upload", "document list", "passed", f"matched={len(page['items'])}")

    status, response = cga.request_json("GET", f"/knowledge/documents/{document_id}", token=state.viewer_token)
    detail = cga.require_dict(cga.api_data("direct document detail", status, response), "direct document detail")
    if detail.get("title") != fields[0][1]:
        raise IntegrationError("document detail did not match uploaded title")
    recorder.add("knowledge upload", "document detail", "passed")

    status, response = cga.request_json(
        "GET",
        f"/knowledge/documents/{document_id}/chunks?page=1&page_size=20",
        token=state.viewer_token,
    )
    chunk_page = cga.require_page(cga.api_data("direct document chunks", status, response), "direct document chunks")
    chunk_text = "\n".join(str(item.get("content", "")) for item in chunk_page["items"])
    if unique_phrase not in chunk_text:
        raise IntegrationError("uploaded document chunks do not contain the unique phrase")
    recorder.add("knowledge upload", "chunk list", "passed", f"chunks={chunk_page['total']}")

    status, response = cga.request_json("POST", f"/knowledge/documents/{document_id}/reparse", token=state.engineer_token)
    reparse = cga.require_dict(cga.api_data("direct document reparse", status, response), "direct document reparse")
    if reparse.get("parse_status") != "parsed" or int(reparse.get("chunk_count") or 0) <= 0:
        raise IntegrationError(f"document reparse failed: {reparse}")
    recorder.add("knowledge upload", "reparse", "passed", f"chunk_count={reparse.get('chunk_count')}")

    status, response = cga.request_json(
        "POST",
        f"/review/knowledge/{document_id}/approve",
        token=state.viewer_token,
        payload={"comment": "viewer should not approve"},
    )
    cga.expect_forbidden("viewer approve direct document", status, response)
    recorder.add("auth/RBAC", "viewer review approve blocked", "passed")

    status, response = cga.request_json(
        "POST",
        f"/review/knowledge/{document_id}/approve",
        token=state.expert_token,
        payload={"comment": "Task21A direct document approved."},
    )
    reviewed = cga.require_dict(cga.api_data("approve direct document", status, response), "approve direct document")
    reviewed_document = reviewed.get("document") if isinstance(reviewed.get("document"), dict) else reviewed
    if reviewed_document.get("review_status") != "approved":
        raise IntegrationError(f"document was not approved: {reviewed}")
    recorder.add("knowledge review", "approve direct document", "passed")

    status, response = cga.request_json(
        "POST",
        "/retrieval/query",
        token=state.viewer_token,
        payload={
            "query": unique_phrase,
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "document_type": "manual",
            "top_k": 5,
            "include_sources": True,
            "enable_model_enhancement": False,
        },
        timeout=90,
    )
    retrieval = cga.require_dict(cga.api_data("direct document retrieval", status, response), "direct document retrieval")
    references = retrieval.get("references") or []
    retrieved_chunks = retrieval.get("retrieved_chunks") or []
    if not references or not retrieved_chunks:
        raise IntegrationError(f"retrieval did not return real references/chunks: {retrieval}")
    if not any(str(ref.get("document_id")) == document_id for ref in references):
        raise IntegrationError("retrieval references did not include the uploaded document")
    trace_id = str(retrieval.get("trace_id") or "")
    if not trace_id:
        raise IntegrationError("retrieval did not return trace_id")
    holder["qa_trace_id"] = trace_id
    recorder.add(
        "retrieval",
        "direct document query references",
        "passed",
        f"trace_id={trace_id}, references={len(references)}, chunks={len(retrieved_chunks)}",
    )

    status, response = cga.request_json("GET", f"/retrieval/records/{trace_id}", token=state.viewer_token)
    qa_record = cga.require_dict(cga.api_data("retrieval record detail", status, response), "retrieval record detail")
    if str(qa_record.get("trace_id")) != trace_id:
        raise IntegrationError("retrieval record detail trace_id mismatch")
    if not qa_record.get("references") or not qa_record.get("suggested_steps"):
        raise IntegrationError("retrieval record did not persist references or suggested_steps")
    recorder.add("records", "qa record persistence", "passed", f"trace_id={trace_id}")


def check_media_permissions(state: cga.AcceptanceState, recorder: cga.Recorder) -> None:
    if not state.media_id:
        raise IntegrationError("media_id is missing; cannot verify viewer OCR permission")
    status, response = cga.request_json("POST", f"/media/{state.media_id}/ocr", token=state.viewer_token)
    cga.expect_forbidden("viewer trigger OCR", status, response)
    recorder.add("auth/RBAC", "viewer OCR trigger blocked", "passed")


def check_kg_candidate_flow(state: cga.AcceptanceState, recorder: cga.Recorder) -> None:
    status, response = cga.request_json("GET", "/kg/candidates?page=1&page_size=1", token=state.expert_token)
    page = cga.require_page(cga.api_data("kg candidate list", status, response), "kg candidate list")
    if not page["items"]:
        recorder.add("knowledge graph", "candidate approve/reject probe", "partial", "no KG candidate available")
        return
    candidate_id = str(page["items"][0].get("id"))
    status, response = cga.request_json(
        "POST",
        f"/kg/candidates/{candidate_id}/reject?{cga.encode_query({'comment': 'Task21A permission probe reject.'})}",
        token=state.viewer_token,
    )
    cga.expect_forbidden("viewer reject KG candidate", status, response)
    recorder.add("auth/RBAC", "viewer KG candidate review blocked", "passed")


def cleanup_direct_document(state: cga.AcceptanceState, recorder: cga.Recorder, holder: dict[str, Any]) -> None:
    document_id = holder.get("document_id")
    if not document_id:
        recorder.add("test data cleanup", "direct document cleanup", "skipped", "document_id missing")
        return
    status, response = cga.request_json("DELETE", f"/knowledge/documents/{document_id}", token=state.engineer_token)
    if status < 400 and response.get("code") in (0, 200):
        recorder.add("test data cleanup", "direct document archive", "passed", f"document_id={document_id}")
        return
    recorder.add("test data cleanup", "direct document archive", "partial", f"http={status}, message={response.get('message')}")


def run() -> tuple[cga.Recorder, cga.AcceptanceState, dict[str, Any]]:
    recorder = cga.Recorder()
    state = cga.AcceptanceState()
    holder: dict[str, Any] = {"run_id": RUN_ID, "marker": MARKER, "api_base_url": API_BASE_URL, "app_base_url": APP_BASE_URL}

    recorder.step("frontend/backend integration", "static scan", lambda: check_static_scan(recorder, holder) or "")
    recorder.step("backend identity", "health and database", lambda: check_backend_identity(recorder) or "")
    recorder.step("auth/RBAC", "setup real users", lambda: setup_task21a_auth(state, recorder) or "")
    if not state.admin_token:
        return recorder, state, holder

    recorder.step("knowledge upload", "direct upload/review/retrieval", lambda: check_direct_document_upload(state, recorder, holder) or "")
    recorder.step("system status", "database online", lambda: cga.check_system(state, recorder) or "")
    recorder.step("devices", "device workflow", lambda: cga.check_devices(state, recorder) or "")
    recorder.step("maintenance records", "device record workflow", lambda: cga.check_maintenance_records(state, recorder) or "")
    recorder.step("media/multimodal", "media and OCR workflow", lambda: cga.check_media_and_ocr(state, recorder) or "")
    recorder.step("auth/RBAC", "viewer OCR permission", lambda: check_media_permissions(state, recorder) or "")
    recorder.step("knowledge contributions", "contribution to document workflow", lambda: cga.check_knowledge_contribution(state, recorder) or "")
    recorder.step("retrieval", "contribution retrieval and QA records", lambda: cga.check_retrieval_and_records(state, recorder) or "")
    recorder.step("diagnosis", "diagnosis workflow", lambda: cga.check_diagnosis(state, recorder) or "")
    recorder.step("SOP", "SOP workflow", lambda: cga.check_sop(state, recorder) or "")
    recorder.step("maintenance tasks", "task workflow", lambda: cga.check_tasks(state, recorder) or "")
    recorder.step("record center", "record center workflow", lambda: cga.check_record_center(state, recorder) or "")
    recorder.step("corrections", "correction workflow", lambda: cga.check_corrections(state, recorder) or "")
    recorder.step("knowledge graph", "KG read and RBAC workflow", lambda: cga.check_knowledge_graph(state, recorder) or "")
    recorder.step("knowledge graph", "candidate review permission", lambda: check_kg_candidate_flow(state, recorder) or "")
    recorder.step("model gateway", "provider status and fallback workflow", lambda: cga.check_model_gateway(state, recorder) or "")
    recorder.step("frontend routes", "SPA fallback", lambda: cga.check_frontend_routes(recorder) or "")
    recorder.step("test data cleanup", "direct document archive", lambda: cleanup_direct_document(state, recorder, holder) or "")
    recorder.step("test data cleanup", "soft archive Task21A data", lambda: cga.cleanup_created_data(state, recorder) or "")
    return recorder, state, holder


def scan_summary(scan: IntegrationScan | None) -> dict[str, Any]:
    if not scan:
        return {}
    return {
        "total_pages": len(scan.frontend_pages),
        "total_frontend_api_functions": len({call.function for call in scan.frontend_api_calls}),
        "total_frontend_api_calls": len(scan.frontend_api_calls),
        "matched_backend_apis": len(scan.matched_calls),
        "missing_apis": [
            {
                "file": call.file,
                "line": call.line,
                "function": call.function,
                "method": call.method,
                "path": call.normalized_path,
            }
            for call in scan.missing_calls
        ],
        "old_api_hits": scan.old_api_hits,
        "fake_hits": scan.fake_hits,
        "page_api_matrix": scan.page_api_matrix,
    }


def print_summary(recorder: cga.Recorder, state: cga.AcceptanceState, holder: dict[str, Any]) -> None:
    scan = holder.get("scan")
    by_status = {
        "passed": recorder.count("passed"),
        "blocked": recorder.count("blocked"),
        "partial": recorder.count("partial"),
        "failed": recorder.count("failed"),
        "skipped": recorder.count("skipped"),
    }
    payload = {
        "status": "failed" if recorder.failed() else "passed",
        "api_base_url": API_BASE_URL,
        "app_base_url": APP_BASE_URL,
        "run_id": RUN_ID,
        "marker": MARKER,
        "summary": {"total": len(recorder.results), **by_status},
        "frontend_api": scan_summary(scan if isinstance(scan, IntegrationScan) else None),
        "created": {
            "direct_document_id": holder.get("document_id"),
            "direct_document_chunk_count": holder.get("chunk_count"),
            "direct_qa_trace_id": holder.get("qa_trace_id"),
            "device_id": state.device_id,
            "media_id": state.media_id,
            "contribution_id": state.contribution_id,
            "contribution_document_id": state.document_id,
            "contribution_chunk_count": state.chunk_count,
            "qa_trace_id": state.qa_trace_id,
            "diagnosis_trace_id": state.diagnosis_trace_id,
            "sop_template_id": state.sop_template_id,
            "sop_execution_id": state.sop_execution_id,
            "task_id": state.task_id,
            "correction_id": state.correction_id,
        },
        "external_status": state.external_status,
        "cleanup_notes": state.cleanup_notes,
        "results": [
            {"area": result.area, "name": result.name, "status": result.status, "notes": result.notes}
            for result in recorder.results
        ],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    try:
        recorder, state, holder = run()
    except Exception as exc:  # noqa: BLE001
        recorder = cga.Recorder()
        state = cga.AcceptanceState()
        holder = {"fatal_error": str(exc)}
        recorder.add("real frontend API integration", "fatal setup error", "failed", str(exc))
    print_summary(recorder, state, holder)
    return 1 if recorder.failed() else 0


if __name__ == "__main__":
    raise SystemExit(main())
