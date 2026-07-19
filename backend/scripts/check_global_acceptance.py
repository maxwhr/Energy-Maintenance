from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib import error, parse, request


API_BASE_URL = os.getenv("GLOBAL_ACCEPTANCE_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
ADMIN_USERNAME = os.getenv("GLOBAL_ACCEPTANCE_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("GLOBAL_ACCEPTANCE_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
TEST_PASSWORD = os.getenv("GLOBAL_ACCEPTANCE_TEST_PASSWORD", "Task18I_pass123")
RUN_ID = os.getenv("GLOBAL_ACCEPTANCE_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task18I_{RUN_ID}"
SAMPLE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAFklEQVR4nGP8//8/A27AhEeOYeRKAwCl4wMRx3ocVQAAAABJRU5ErkJggg=="
)


class AcceptanceError(AssertionError):
    pass


@dataclass(slots=True)
class CheckResult:
    area: str
    name: str
    status: str
    notes: str = ""


@dataclass(slots=True)
class AcceptanceState:
    admin_token: str | None = None
    expert_token: str | None = None
    engineer_token: str | None = None
    viewer_token: str | None = None
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    device_id: str | None = None
    media_id: str | None = None
    contribution_id: str | None = None
    document_id: str | None = None
    chunk_count: int = 0
    qa_trace_id: str | None = None
    diagnosis_trace_id: str | None = None
    sop_template_id: str | None = None
    sop_execution_id: str | None = None
    task_id: str | None = None
    maintenance_record_id: str | None = None
    correction_id: str | None = None
    external_status: dict[str, str] = field(default_factory=dict)
    cleanup_notes: list[str] = field(default_factory=list)


class Recorder:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def add(self, area: str, name: str, status: str, notes: str = "") -> None:
        if status not in {"passed", "blocked", "partial", "failed", "skipped"}:
            raise ValueError(f"Invalid check status: {status}")
        self.results.append(CheckResult(area=area, name=name, status=status, notes=notes))
        print(f"[{status}] {area} - {name}: {notes}")

    def step(self, area: str, name: str, fn: Callable[[], str | None]) -> None:
        try:
            notes = fn() or ""
            self.add(area, name, "passed", notes)
        except Exception as exc:  # noqa: BLE001 - final acceptance script must continue and summarize.
            self.add(area, name, "failed", str(exc))

    def count(self, status: str) -> int:
        return sum(1 for result in self.results if result.status == status)

    def failed(self) -> list[CheckResult]:
        return [result for result in self.results if result.status == "failed"]


def request_json(
    method: str,
    path_or_url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str = "application/json",
    timeout: int = 60,
) -> tuple[int, dict[str, Any]]:
    url = path_or_url if path_or_url.startswith("http") else f"{API_BASE_URL}{path_or_url}"
    data = body
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif body is not None:
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {"code": exc.code, "message": exc.reason, "data": None}
        except json.JSONDecodeError:
            parsed = {"code": exc.code, "message": raw[:500], "data": None}
        return exc.code, parsed


def request_raw(path_or_url: str, *, token: str | None = None, timeout: int = 30) -> tuple[int, bytes, str]:
    url = path_or_url if path_or_url.startswith("http") else f"{API_BASE_URL}{path_or_url}"
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get("content-type", "")
    except error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("content-type", "")


def api_data(label: str, status: int, response: dict[str, Any]) -> Any:
    if status >= 400 or response.get("code") not in (0, 200):
        raise AcceptanceError(f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}")
    return response.get("data")


def expect_forbidden(label: str, status: int, response: dict[str, Any]) -> None:
    code = response.get("code")
    if status in (401, 403) or (isinstance(code, int) and code not in (0, 200)):
        return
    raise AcceptanceError(f"{label} should be forbidden, got http={status}, code={code}")


def encode_query(params: dict[str, Any]) -> str:
    return parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})


def login(username: str, password: str) -> tuple[str, dict[str, Any]]:
    status, response = request_json("POST", "/auth/login", payload={"username": username, "password": password})
    data = api_data(f"login {username}", status, response)
    token = data.get("access_token") if isinstance(data, dict) else None
    user = data.get("user") if isinstance(data, dict) else None
    if not token or not isinstance(user, dict):
        raise AcceptanceError(f"login {username} did not return token and user")
    return str(token), user


def ensure_user(admin_token: str, username: str, role: str, display_name: str) -> dict[str, Any]:
    query = encode_query({"keyword": username, "page": 1, "page_size": 20})
    status, response = request_json("GET", f"/users?{query}", token=admin_token)
    page = api_data(f"list user {username}", status, response)
    items = page.get("items") if isinstance(page, dict) else []
    match = next((item for item in items if item.get("username") == username), None)
    payload = {
        "display_name": display_name,
        "role": role,
        "status": "active",
        "password": TEST_PASSWORD,
    }
    if match:
        status, response = request_json("PUT", f"/users/{match['id']}", token=admin_token, payload=payload)
        return api_data(f"update user {username}", status, response)
    create_payload = {
        "username": username,
        "password": TEST_PASSWORD,
        "display_name": display_name,
        "role": role,
        "status": "active",
    }
    status, response = request_json("POST", "/users", token=admin_token, payload=create_payload)
    return api_data(f"create user {username}", status, response)


def multipart_body(fields: list[tuple[str, str]], file_field: str, file_name: str, file_bytes: bytes, mime: str) -> tuple[bytes, str]:
    boundary = f"----EnergyMaintenanceTask18I{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields:
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
        .encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AcceptanceError(f"{label} did not return an object")
    return value


def require_page(value: Any, label: str) -> dict[str, Any]:
    page = require_dict(value, label)
    if "items" not in page or "total" not in page:
        raise AcceptanceError(f"{label} did not return a page")
    return page


def setup_auth(state: AcceptanceState, recorder: Recorder) -> None:
    token, admin_user = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    state.admin_token = token
    state.users["admin"] = admin_user
    recorder.add("auth/RBAC", "admin login", "passed", f"user={admin_user.get('username')}")

    for role in ("engineer", "expert", "viewer"):
        username = f"Task18I_{role}"
        user = ensure_user(token, username, role, f"Task18I {role}")
        state.users[role] = user
        role_token, _ = login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", role_token)
        recorder.add("auth/RBAC", f"{role} account ready", "passed", f"id={user.get('id')}")

    for label, token_value in (
        ("admin", state.admin_token),
        ("expert", state.expert_token),
        ("engineer", state.engineer_token),
        ("viewer", state.viewer_token),
    ):
        status, response = request_json("GET", "/auth/me", token=token_value)
        user = api_data(f"auth/me {label}", status, response)
        if not isinstance(user, dict) or not user.get("username"):
            raise AcceptanceError(f"auth/me {label} returned invalid user")
        recorder.add("auth/RBAC", f"auth/me {label}", "passed", f"role={user.get('role')}")


def check_system(state: AcceptanceState, recorder: Recorder) -> None:
    status, response = request_json("GET", "/system/status", token=state.admin_token)
    data = api_data("system status", status, response)
    database_status = require_dict(data, "system status").get("database_status")
    if database_status != "online":
        raise AcceptanceError(f"database_status is {database_status!r}, expected online")
    recorder.add("system status", "database status", "passed", f"database_status={database_status}")


def check_devices(state: AcceptanceState, recorder: Recorder) -> None:
    status, response = request_json("GET", "/devices/statistics/summary", token=state.admin_token)
    api_data("device statistics", status, response)
    recorder.add("devices", "statistics summary", "passed")

    payload = {
        "device_code": f"{MARKER}_DEV",
        "device_name": f"{MARKER} Huawei SUN2000 inverter",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-50KTL",
        "device_type": "pv_inverter",
        "station_name": f"{MARKER} demo station",
        "location": "Task18I acceptance bay",
        "status": "normal",
        "metadata_json": {"marker": MARKER},
        "description": f"{MARKER} device created for global acceptance.",
    }
    status, response = request_json("POST", "/devices", token=state.engineer_token, payload=payload)
    device = require_dict(api_data("create device", status, response), "create device")
    state.device_id = str(device["id"])
    recorder.add("devices", "create", "passed", f"device_id={state.device_id}")

    status, response = request_json("GET", f"/devices/{state.device_id}", token=state.viewer_token)
    detail = require_dict(api_data("device detail", status, response), "device detail")
    if detail.get("device_code") != payload["device_code"]:
        raise AcceptanceError("device detail did not match created device")
    recorder.add("devices", "detail", "passed", detail.get("device_code", ""))

    status, response = request_json("GET", f"/devices?{encode_query({'keyword': MARKER, 'page': 1, 'page_size': 5})}", token=state.admin_token)
    page = require_page(api_data("device list", status, response), "device list")
    if not page["items"]:
        raise AcceptanceError("device list did not include Task18I device")
    recorder.add("devices", "list", "passed", f"matched={len(page['items'])}")

    status, response = request_json("POST", "/devices", token=state.viewer_token, payload=payload)
    expect_forbidden("viewer create device", status, response)
    recorder.add("auth/RBAC", "viewer write device blocked", "passed")


def check_maintenance_records(state: AcceptanceState, recorder: Recorder) -> None:
    if not state.device_id:
        recorder.add("maintenance records", "device maintenance record", "skipped", "device was not created")
        return
    payload = {
        "fault_type": "low_insulation_resistance",
        "alarm_code": f"{MARKER}_ALARM",
        "fault_description": f"{MARKER} low insulation alarm record.",
        "root_cause": "Cable terminal moisture ingress verification.",
        "repair_action": "Cleaned connector, dried cabinet, and retested insulation.",
        "replaced_parts": "None",
        "verification_result": "Insulation value returned to normal acceptance range.",
        "is_recurrent": False,
        "metadata_json": {"marker": MARKER},
    }
    status, response = request_json("POST", f"/devices/{state.device_id}/maintenance-records", token=state.engineer_token, payload=payload)
    record = require_dict(api_data("create maintenance record", status, response), "create maintenance record")
    state.maintenance_record_id = str(record["id"])
    recorder.add("maintenance records", "create", "passed", f"id={state.maintenance_record_id}")

    status, response = request_json("GET", f"/devices/{state.device_id}/maintenance-records?page=1&page_size=5", token=state.viewer_token)
    page = require_page(api_data("list maintenance records", status, response), "list maintenance records")
    if not page["items"]:
        raise AcceptanceError("maintenance record list is empty")
    recorder.add("maintenance records", "list", "passed", f"total={page['total']}")


def check_media_and_ocr(state: AcceptanceState, recorder: Recorder) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} tiny image media acceptance sample"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
        ("fault_type", "low_insulation_resistance"),
        ("alarm_code", f"{MARKER}_ALARM"),
    ]
    if state.device_id:
        fields.append(("device_id", state.device_id))
    body, content_type = multipart_body(fields, "file", f"{MARKER}_sample.png", SAMPLE_PNG, "image/png")
    status, response = request_json(
        "POST",
        "/media/upload",
        token=state.engineer_token,
        body=body,
        content_type=content_type,
        timeout=90,
    )
    media = require_dict(api_data("media upload", status, response), "media upload")
    state.media_id = str(media.get("media_id") or media.get("id"))
    if not state.media_id:
        raise AcceptanceError("media upload did not return media_id")
    recorder.add("media/multimodal", "upload", "passed", f"media_id={state.media_id}")

    status, response = request_json("GET", f"/media?{encode_query({'keyword': MARKER, 'page': 1, 'page_size': 5})}", token=state.viewer_token)
    page = require_page(api_data("media list", status, response), "media list")
    if not page["items"]:
        raise AcceptanceError("media list did not include uploaded media")
    recorder.add("media/multimodal", "list", "passed", f"matched={len(page['items'])}")

    status, response = request_json("GET", f"/media/{state.media_id}", token=state.viewer_token)
    api_data("media detail", status, response)
    recorder.add("media/multimodal", "detail", "passed")

    raw_status, body_bytes, content_type = request_raw(f"/media/{state.media_id}/content", token=state.viewer_token)
    if raw_status != 200 or not body_bytes:
        raise AcceptanceError(f"media content returned status={raw_status}, bytes={len(body_bytes)}")
    recorder.add("media/multimodal", "content preview", "passed", f"content_type={content_type}")

    status, response = request_json("GET", "/media/ocr/status", token=state.viewer_token)
    ocr_status = require_dict(api_data("ocr status", status, response), "ocr status")
    status_value = str(ocr_status.get("status"))
    state.external_status["ocr"] = status_value
    if status_value in {"disabled", "not_configured"}:
        recorder.add("OCR optional", "engine status", "blocked", f"status={status_value}")
    elif status_value == "available":
        recorder.add("OCR optional", "engine status", "passed", "status=available")
    else:
        recorder.add("OCR optional", "engine status", "partial", f"status={status_value}")

    status, response = request_json("GET", f"/media/{state.media_id}/ocr", token=state.viewer_token)
    api_data("media ocr detail", status, response)
    recorder.add("OCR optional", "media OCR detail", "passed")


def check_knowledge_contribution(state: AcceptanceState, recorder: Recorder) -> None:
    unique_phrase = f"{MARKER} pv inverter insulation alarm acceptance phrase"
    payload = {
        "title": f"{MARKER} SUN2000 low insulation maintenance contribution",
        "content": (
            f"{unique_phrase}. Huawei SUN2000 PV inverter reports low insulation resistance after rain. "
            "Check DC cables, combiner terminals, string insulation, moisture ingress, and cabinet grounding. "
            "Power isolation and lockout must be confirmed before opening the cabinet."
        ),
        "contribution_type": "maintenance_experience",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "device_id": state.device_id,
        "source_type": "Task18I_global_acceptance",
        "source_trace_id": f"{MARKER}_CONTRIBUTION",
        "fault_type": "low_insulation_resistance",
        "alarm_code": f"{MARKER}_ALARM",
        "symptom_description": f"{MARKER} alarm appears before grid connection.",
        "diagnosis_process": "Verify environment, DC insulation, and inverter terminal status.",
        "root_cause": "Moisture-related insulation degradation was suspected.",
        "solution": "Dry and inspect strings, then retest insulation before restarting.",
        "tools_used": ["insulation tester", "multimeter"],
        "parts_used": [],
        "safety_notes": ["Confirm DC and AC isolation before inspection."],
        "media_ids": [state.media_id] if state.media_id else [],
        "metadata_json": {"marker": MARKER},
    }
    status, response = request_json("POST", "/knowledge/contributions", token=state.engineer_token, payload=payload)
    contribution = require_dict(api_data("create contribution", status, response), "create contribution")
    state.contribution_id = str(contribution["id"])
    recorder.add("knowledge contributions", "engineer create", "passed", f"id={state.contribution_id}")

    status, response = request_json("POST", f"/knowledge/contributions/{state.contribution_id}/submit", token=state.engineer_token)
    api_data("submit contribution", status, response)
    recorder.add("knowledge contributions", "engineer submit", "passed")

    status, response = request_json(
        "POST",
        f"/knowledge/contributions/{state.contribution_id}/approve",
        token=state.engineer_token,
        payload={"comment": "engineer should not approve"},
    )
    expect_forbidden("engineer approve contribution", status, response)
    recorder.add("auth/RBAC", "engineer review blocked", "passed")

    status, response = request_json(
        "POST",
        f"/knowledge/contributions/{state.contribution_id}/approve",
        token=state.expert_token,
        payload={"comment": "Task18I expert approval"},
    )
    api_data("expert approve contribution", status, response)
    recorder.add("knowledge contributions", "expert approve", "passed")

    status, response = request_json(
        "POST",
        f"/knowledge/contributions/{state.contribution_id}/convert-to-document",
        token=state.expert_token,
        payload={"comment": "Task18I convert approved contribution"},
        timeout=90,
    )
    converted = require_dict(api_data("convert contribution", status, response), "convert contribution")
    document = require_dict(converted.get("document"), "converted document")
    state.document_id = str(document["id"])
    state.chunk_count = int(converted.get("chunk_count") or document.get("chunk_count") or 0)
    if state.chunk_count <= 0:
        raise AcceptanceError("converted contribution did not create chunks")
    recorder.add("knowledge contributions", "convert to document", "passed", f"document_id={state.document_id}, chunks={state.chunk_count}")

    status, response = request_json("GET", f"/knowledge/documents/{state.document_id}", token=state.viewer_token)
    document_detail = require_dict(api_data("knowledge document detail", status, response), "knowledge document detail")
    if document_detail.get("review_status") != "approved" or document_detail.get("parse_status") != "parsed":
        raise AcceptanceError(
            f"converted document status unexpected: review={document_detail.get('review_status')}, parse={document_detail.get('parse_status')}"
        )
    recorder.add("knowledge documents", "detail approved parsed", "passed")

    status, response = request_json("GET", f"/knowledge/documents/{state.document_id}/chunks?page=1&page_size=5", token=state.viewer_token)
    chunks = require_page(api_data("knowledge chunks", status, response), "knowledge chunks")
    if not chunks["items"] or unique_phrase not in json.dumps(chunks["items"], ensure_ascii=False):
        raise AcceptanceError("knowledge chunks do not contain Task18I contribution content")
    recorder.add("knowledge documents", "chunks", "passed", f"total={chunks['total']}")

    status, response = request_json(
        "GET",
        f"/review/knowledge?{encode_query({'keyword': MARKER, 'page': 1, 'page_size': 10})}",
        token=state.expert_token,
    )
    page = require_page(api_data("knowledge review list", status, response), "knowledge review list")
    if not page["items"]:
        raise AcceptanceError("knowledge review list did not show converted document")
    recorder.add("knowledge review", "list", "passed", f"matched={len(page['items'])}")


def check_retrieval_and_records(state: AcceptanceState, recorder: Recorder) -> None:
    payload = {
        "query": f"{MARKER} How to inspect Huawei SUN2000 low insulation alarm?",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "alarm_code": f"{MARKER}_ALARM",
        "media_ids": [state.media_id] if state.media_id else [],
        "use_ocr_text": False,
        "top_k": 5,
        "enable_kg_enhancement": True,
        "enable_model_enhancement": False,
    }
    status, response = request_json("POST", "/retrieval/query", token=state.engineer_token, payload=payload, timeout=90)
    result = require_dict(api_data("retrieval query", status, response), "retrieval query")
    state.qa_trace_id = result.get("trace_id")
    references = result.get("references") or []
    retrieved = result.get("retrieved_chunks") or []
    if not state.qa_trace_id or not references or not retrieved:
        raise AcceptanceError("retrieval did not return trace_id, references, and retrieved chunks")
    if not any(str(item.get("document_id")) == state.document_id for item in references):
        raise AcceptanceError("retrieval references did not include Task18I document")
    if "kg_context" not in result:
        raise AcceptanceError("retrieval did not include kg_context when KG enhancement was enabled")
    recorder.add("retrieval", "query with real references", "passed", f"trace_id={state.qa_trace_id}, refs={len(references)}")

    status, response = request_json("GET", f"/retrieval/records/{state.qa_trace_id}", token=state.viewer_token)
    api_data("retrieval record detail", status, response)
    recorder.add("retrieval", "record detail", "passed")

    status, response = request_json(
        "GET",
        f"/retrieval/records?{encode_query({'keyword': MARKER, 'page': 1, 'page_size': 10})}",
        token=state.admin_token,
    )
    page = require_page(api_data("retrieval records list", status, response), "retrieval records list")
    if not page["items"]:
        raise AcceptanceError("retrieval records did not include Task18I query")
    recorder.add("record center", "qa_records persistence", "passed", f"matched={len(page['items'])}")


def check_diagnosis(state: AcceptanceState, recorder: Recorder) -> None:
    payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-50KTL",
        "device_type": "pv_inverter",
        "device_id": state.device_id,
        "fault_type": "low_insulation_resistance",
        "alarm_code": f"{MARKER}_ALARM",
        "fault_description": f"{MARKER} SUN2000 reports low insulation resistance before grid connection.",
        "observed_symptoms": ["rainy weather", "alarm before startup"],
        "media_ids": [state.media_id] if state.media_id else [],
        "use_ocr_text": False,
        "enable_kg_enhancement": True,
        "enable_model_enhancement": False,
    }
    status, response = request_json("POST", "/diagnosis/analyze", token=state.engineer_token, payload=payload, timeout=90)
    diagnosis = require_dict(api_data("diagnosis analyze", status, response), "diagnosis analyze")
    state.diagnosis_trace_id = diagnosis.get("trace_id")
    if not state.diagnosis_trace_id or not diagnosis.get("safety_notes"):
        raise AcceptanceError("diagnosis did not return trace_id and safety_notes")
    if "kg_context" not in diagnosis:
        raise AcceptanceError("diagnosis did not include kg_context when KG enhancement was enabled")
    recorder.add("diagnosis", "analyze", "passed", f"trace_id={state.diagnosis_trace_id}")

    status, response = request_json("GET", f"/diagnosis/records/{state.diagnosis_trace_id}", token=state.viewer_token)
    api_data("diagnosis record detail", status, response)
    recorder.add("diagnosis", "record detail", "passed")


def check_sop(state: AcceptanceState, recorder: Recorder) -> None:
    template_payload = {
        "title": f"{MARKER} SUN2000 low insulation SOP",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "maintenance_level": "level_2",
        "status": "active",
        "version": 1,
        "steps": [
            {
                "step_index": 1,
                "step_title": "Safety isolation",
                "instruction": "Confirm AC and DC isolation before opening the inverter cabinet.",
                "expected_result": "No energized circuit remains exposed.",
                "safety_note": "Use lockout and tagout.",
            },
            {
                "step_index": 2,
                "step_title": "Insulation inspection",
                "instruction": "Inspect DC strings and terminals for moisture or insulation damage.",
                "expected_result": "Insulation resistance returns to acceptable range.",
            },
        ],
        "safety_requirements": [{"item": "Wear insulated gloves and confirm no live work."}],
        "tools_required": [{"name": "insulation tester"}],
        "materials_required": [],
        "compliance_notes": f"{MARKER} generated acceptance SOP template.",
        "metadata_json": {"marker": MARKER},
    }
    status, response = request_json("POST", "/sop/templates", token=state.expert_token, payload=template_payload)
    template = require_dict(api_data("create SOP template", status, response), "create SOP template")
    state.sop_template_id = str(template["id"])
    recorder.add("SOP", "template create", "passed", f"id={state.sop_template_id}")

    status, response = request_json(
        "POST",
        "/sop/generate",
        token=state.engineer_token,
        payload={
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "model": "SUN2000-50KTL",
            "device_type": "pv_inverter",
            "fault_type": "low_insulation_resistance",
            "maintenance_level": "level_2",
            "include_references": True,
            "enable_kg_enhancement": True,
            "enable_model_enhancement": False,
        },
        timeout=90,
    )
    sop = require_dict(api_data("generate SOP", status, response), "generate SOP")
    if not sop.get("steps"):
        raise AcceptanceError("generated SOP did not include steps")
    if "kg_context" not in sop:
        raise AcceptanceError("SOP did not include kg_context when KG enhancement was enabled")
    recorder.add("SOP", "generate with KG enhancement", "passed", f"source={sop.get('source')}")

    status, response = request_json(
        "POST",
        "/sop/executions",
        token=state.engineer_token,
        payload={
            "template_id": state.sop_template_id,
            "status": "not_started",
            "metadata_json": {"marker": MARKER},
        },
    )
    execution = require_dict(api_data("create SOP execution", status, response), "create SOP execution")
    state.sop_execution_id = str(execution["id"])
    recorder.add("SOP", "execution create", "passed", f"id={state.sop_execution_id}")

    status, response = request_json(
        "PUT",
        f"/sop/executions/{state.sop_execution_id}",
        token=state.engineer_token,
        payload={
            "status": "in_progress",
            "step_results": [{"step_index": 1, "step_title": "Safety isolation", "checked": True}],
            "abnormal_notes": f"{MARKER} execution started.",
        },
    )
    api_data("start SOP execution", status, response)

    status, response = request_json(
        "PUT",
        f"/sop/executions/{state.sop_execution_id}",
        token=state.engineer_token,
        payload={
            "status": "completed",
            "step_results": [{"step_index": 1, "step_title": "Safety isolation", "checked": True}],
            "abnormal_notes": f"{MARKER} execution accepted.",
        },
    )
    api_data("update SOP execution", status, response)
    recorder.add("SOP", "execution complete", "passed")


def check_tasks(state: AcceptanceState, recorder: Recorder) -> None:
    payload = {
        "device_id": state.device_id,
        "diagnosis_trace_id": state.diagnosis_trace_id,
        "qa_trace_id": state.qa_trace_id,
        "sop_template_id": state.sop_template_id,
        "sop_execution_id": state.sop_execution_id,
        "title": f"{MARKER} low insulation work order",
        "fault_type": "low_insulation_resistance",
        "alarm_code": f"{MARKER}_ALARM",
        "fault_description": f"{MARKER} generated from global acceptance.",
        "priority": "medium",
        "remark": f"{MARKER} task acceptance.",
    }
    status, response = request_json("POST", "/maintenance/tasks", token=state.engineer_token, payload=payload)
    task = require_dict(api_data("create task", status, response), "create task")
    state.task_id = str(task["id"])
    recorder.add("maintenance tasks", "create", "passed", f"id={state.task_id}")

    engineer_id = state.users["engineer"]["id"]
    status, response = request_json(
        "POST",
        f"/maintenance/tasks/{state.task_id}/assign",
        token=state.viewer_token,
        payload={"assignee_id": engineer_id},
    )
    expect_forbidden("viewer assign task", status, response)
    recorder.add("auth/RBAC", "viewer assign blocked", "passed")

    status, response = request_json(
        "POST",
        f"/maintenance/tasks/{state.task_id}/assign",
        token=state.expert_token,
        payload={"assignee_id": engineer_id},
    )
    api_data("assign task", status, response)
    recorder.add("maintenance tasks", "assign", "passed")

    status, response = request_json("POST", f"/maintenance/tasks/{state.task_id}/start", token=state.engineer_token)
    api_data("start task", status, response)
    recorder.add("maintenance tasks", "start", "passed")

    status, response = request_json(
        "POST",
        f"/maintenance/tasks/{state.task_id}/complete",
        token=state.engineer_token,
        payload={
            "root_cause": "Task18I suspected moisture at DC terminal.",
            "repair_action": "Task18I dried terminal and verified insulation.",
            "replaced_parts": [],
            "verification_result": "Task18I alarm cleared after verification.",
            "is_recurrent": False,
            "maintenance_record_remark": f"{MARKER} completion generated maintenance record.",
            "media_ids": [state.media_id] if state.media_id else [],
        },
    )
    completed = require_dict(api_data("complete task", status, response), "complete task")
    state.maintenance_record_id = str(completed.get("maintenance_record", {}).get("id") or state.maintenance_record_id or "")
    recorder.add("maintenance tasks", "complete", "passed", f"maintenance_record_id={state.maintenance_record_id or 'not_returned'}")

    status, response = request_json("GET", f"/maintenance/tasks/{state.task_id}", token=state.viewer_token)
    detail = require_dict(api_data("task detail", status, response), "task detail")
    if require_dict(detail.get("task"), "task detail.task").get("status") != "completed":
        raise AcceptanceError("task detail status is not completed")
    recorder.add("maintenance tasks", "detail", "passed")


def check_record_center(state: AcceptanceState, recorder: Recorder) -> None:
    status, response = request_json("GET", "/record-center/overview", token=state.viewer_token)
    api_data("record center overview", status, response)
    recorder.add("record center", "overview", "passed")

    status, response = request_json(
        "GET",
        f"/record-center/search?{encode_query({'keyword': MARKER, 'page': 1, 'page_size': 20})}",
        token=state.viewer_token,
    )
    page = require_page(api_data("record center search", status, response), "record center search")
    if not page["items"]:
        raise AcceptanceError("record center search did not find Task18I records")
    recorder.add("record center", "search", "passed", f"matched={len(page['items'])}")

    if state.qa_trace_id:
        status, response = request_json(
            "GET",
            f"/record-center/search?{encode_query({'record_type': 'qa', 'trace_id': state.qa_trace_id, 'page': 1, 'page_size': 5})}",
            token=state.viewer_token,
        )
        qa_page = require_page(api_data("record center qa search", status, response), "record center qa search")
        if qa_page["items"]:
            first_item = qa_page["items"][0]
            record_id = first_item.get("id") or first_item.get("record_id") or first_item.get("source_id")
            if not record_id:
                raise AcceptanceError(f"record center qa item does not include record id: {first_item}")
            status, response = request_json("GET", f"/record-center/records/qa/{record_id}", token=state.viewer_token)
            api_data("record center qa detail", status, response)
            recorder.add("record center", "qa detail", "passed", f"id={record_id}")
        else:
            recorder.add("record center", "qa detail", "partial", "qa trace search returned no item")

    if state.device_id:
        status, response = request_json("GET", f"/record-center/devices/{state.device_id}/timeline?limit=20", token=state.viewer_token)
        timeline = require_dict(api_data("device timeline", status, response), "device timeline")
        if "items" not in timeline and "timeline" not in timeline:
            raise AcceptanceError("device timeline payload did not include timeline items")
        recorder.add("record center", "device timeline", "passed")


def check_corrections(state: AcceptanceState, recorder: Recorder) -> None:
    if not state.qa_trace_id:
        recorder.add("corrections", "create", "skipped", "qa_trace_id missing")
        return
    payload = {
        "source_type": "qa",
        "source_trace_id": state.qa_trace_id,
        "original_output": {"answer": f"{MARKER} original acceptance output"},
        "corrected_output": {"answer": f"{MARKER} corrected acceptance output"},
        "reason": f"{MARKER} correction acceptance.",
        "correction_type": "answer_correction",
    }
    status, response = request_json("POST", "/corrections", token=state.engineer_token, payload=payload)
    correction = require_dict(api_data("create correction", status, response), "create correction")
    state.correction_id = str(correction["id"])
    recorder.add("corrections", "create", "passed", f"id={state.correction_id}")

    status, response = request_json(
        "POST",
        f"/corrections/{state.correction_id}/resolve",
        token=state.expert_token,
        payload={"action": "accept", "review_comment": "Task18I accepted."},
    )
    api_data("resolve correction", status, response)
    recorder.add("corrections", "resolve", "passed")

    status, response = request_json("GET", f"/corrections?{encode_query({'keyword': MARKER, 'page': 1, 'page_size': 10})}", token=state.viewer_token)
    page = require_page(api_data("correction list", status, response), "correction list")
    if not page["items"]:
        raise AcceptanceError("correction list did not include Task18I correction")
    recorder.add("corrections", "list", "passed", f"matched={len(page['items'])}")


def check_knowledge_graph(state: AcceptanceState, recorder: Recorder) -> None:
    for name, path in (
        ("overview", "/kg/overview"),
        ("graph", f"/kg/graph?{encode_query({'manufacturer': 'huawei', 'product_series': 'SUN2000', 'limit': 30})}"),
        (
            "business context",
            f"/kg/business-context?{encode_query({'manufacturer': 'huawei', 'product_series': 'SUN2000', 'fault_type': 'low_insulation_resistance', 'question': MARKER})}",
        ),
        ("search", f"/kg/search?{encode_query({'keyword': 'SUN2000', 'page': 1, 'page_size': 10})}"),
    ):
        status, response = request_json("GET", path, token=state.viewer_token)
        api_data(f"kg {name}", status, response)
        recorder.add("knowledge graph", name, "passed")

    status, response = request_json(
        "POST",
        "/kg/nodes",
        token=state.viewer_token,
        payload={
            "node_type": "fault",
            "canonical_name": f"{MARKER}_viewer_forbidden",
            "display_name": f"{MARKER} viewer forbidden",
            "device_type": "pv_inverter",
        },
    )
    expect_forbidden("viewer create kg node", status, response)
    recorder.add("auth/RBAC", "viewer KG write blocked", "passed")


def check_model_gateway(state: AcceptanceState, recorder: Recorder) -> None:
    status, response = request_json("GET", "/model-gateway/status", token=state.admin_token)
    gateway_status = require_dict(api_data("model gateway status", status, response), "model gateway status")
    providers = gateway_status.get("providers") or []
    recorder.add("model gateway", "status", "passed", f"providers={len(providers)}")
    for provider in providers:
        provider_key = provider.get("provider")
        availability = provider.get("availability_status")
        if provider_key in {"cloud_openai", "local_llama_cpp"}:
            state.external_status[provider_key] = str(availability)

    status, response = request_json(
        "POST",
        "/model-gateway/test",
        token=state.admin_token,
        payload={
            "provider": "rule_based",
            "task_type": "qa",
            "allow_fallback": True,
            "prompt": f"{MARKER} rule based safety reminder.",
        },
    )
    data = require_dict(api_data("rule based model test", status, response), "rule based model test")
    if data.get("provider") != "rule_based" or not data.get("trace_id"):
        raise AcceptanceError("rule_based gateway test did not return rule_based trace_id")
    recorder.add("model gateway", "rule_based", "passed", f"trace_id={data.get('trace_id')}")

    for provider in ("cloud_openai", "local_llama_cpp"):
        status, response = request_json(
            "POST",
            "/model-gateway/test",
            token=state.admin_token,
            payload={
                "provider": provider,
                "task_type": "qa",
                "allow_fallback": True,
                "prompt": f"{MARKER} verify fallback for {provider}.",
            },
            timeout=90,
        )
        data = require_dict(api_data(f"{provider} model fallback", status, response), f"{provider} model fallback")
        if data.get("provider") == provider and data.get("success") and not data.get("fallback_used"):
            recorder.add("model gateway", provider, "passed", f"real provider available trace_id={data.get('trace_id')}")
        elif data.get("provider") == "rule_based" and data.get("fallback_used"):
            recorder.add("model gateway", provider, "blocked", f"fallback trace_id={data.get('trace_id')}")
        else:
            raise AcceptanceError(f"{provider} did not return clear real or fallback status: {data}")


def check_frontend_routes(recorder: Recorder) -> None:
    routes = [
        "/",
        "/dashboard",
        "/knowledge/documents",
        "/knowledge/contributions",
        "/knowledge/graph",
        "/assistant/chat",
        "/diagnosis",
        "/sop",
        "/workorder/list",
        "/trace",
        "/model-service",
        "/system",
    ]
    failures: list[str] = []
    for route in routes:
        try:
            with request.urlopen(f"{APP_BASE_URL}{route}", timeout=20) as response:
                body = response.read(200)
                if response.status < 200 or response.status >= 400 or not body:
                    failures.append(f"{route}: status={response.status}, bytes={len(body)}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{route}: {exc}")
    if failures:
        raise AcceptanceError("; ".join(failures))
    recorder.add("frontend routes", "SPA fallback routes", "passed", f"routes={len(routes)}")


def cleanup_created_data(state: AcceptanceState, recorder: Recorder) -> None:
    if state.sop_template_id:
        status, response = request_json("POST", f"/sop/templates/{state.sop_template_id}/archive", token=state.expert_token)
        if status < 400 and response.get("code") in (0, 200):
            state.cleanup_notes.append(f"sop_template archived: {state.sop_template_id}")
    if state.contribution_id:
        status, response = request_json(
            "POST",
            f"/knowledge/contributions/{state.contribution_id}/archive",
            token=state.expert_token,
            payload={"comment": "Task18I cleanup archive."},
        )
        if status < 400 and response.get("code") in (0, 200):
            state.cleanup_notes.append(f"contribution archived: {state.contribution_id}")
    if state.document_id:
        status, response = request_json(
            "POST",
            f"/review/knowledge/{state.document_id}/archive",
            token=state.expert_token,
            payload={"comment": "Task18I cleanup archive."},
        )
        if status < 400 and response.get("code") in (0, 200):
            state.cleanup_notes.append(f"document archived: {state.document_id}")
    if state.device_id:
        status, response = request_json("POST", f"/devices/{state.device_id}/retire", token=state.expert_token)
        if status < 400 and response.get("code") in (0, 200):
            state.cleanup_notes.append(f"device retired: {state.device_id}")
    for role, user in state.users.items():
        if role == "admin":
            continue
        user_id = user.get("id")
        if not user_id:
            continue
        status, response = request_json("POST", f"/users/{user_id}/disable", token=state.admin_token)
        if status < 400 and response.get("code") in (0, 200):
            state.cleanup_notes.append(f"user disabled: {user.get('username')}")
    recorder.add("test data cleanup", "endpoint cleanup", "passed", "; ".join(state.cleanup_notes) or "no endpoint cleanup actions")


def run() -> tuple[Recorder, AcceptanceState]:
    state = AcceptanceState()
    recorder = Recorder()

    setup_auth(state, recorder)
    recorder.step("system status", "database online", lambda: check_system(state, recorder) or "")
    recorder.step("devices", "device workflow", lambda: check_devices(state, recorder) or "")
    recorder.step("maintenance records", "device record workflow", lambda: check_maintenance_records(state, recorder) or "")
    recorder.step("media/multimodal", "media and OCR workflow", lambda: check_media_and_ocr(state, recorder) or "")
    recorder.step("knowledge contributions", "contribution to document workflow", lambda: check_knowledge_contribution(state, recorder) or "")
    recorder.step("retrieval", "retrieval and QA records", lambda: check_retrieval_and_records(state, recorder) or "")
    recorder.step("diagnosis", "diagnosis workflow", lambda: check_diagnosis(state, recorder) or "")
    recorder.step("SOP", "SOP workflow", lambda: check_sop(state, recorder) or "")
    recorder.step("maintenance tasks", "task workflow", lambda: check_tasks(state, recorder) or "")
    recorder.step("record center", "record center workflow", lambda: check_record_center(state, recorder) or "")
    recorder.step("corrections", "correction workflow", lambda: check_corrections(state, recorder) or "")
    recorder.step("knowledge graph", "KG read and RBAC workflow", lambda: check_knowledge_graph(state, recorder) or "")
    recorder.step("model gateway", "provider status and fallback workflow", lambda: check_model_gateway(state, recorder) or "")
    recorder.step("frontend routes", "SPA fallback", lambda: check_frontend_routes(recorder) or "")
    recorder.step("test data cleanup", "soft archive Task18I data", lambda: cleanup_created_data(state, recorder) or "")
    return recorder, state


def print_summary(recorder: Recorder, state: AcceptanceState) -> None:
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
        "summary": {
            "total": len(recorder.results),
            **by_status,
        },
        "created": {
            "device_id": state.device_id,
            "media_id": state.media_id,
            "contribution_id": state.contribution_id,
            "document_id": state.document_id,
            "chunk_count": state.chunk_count,
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
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    try:
        recorder, state = run()
    except Exception as exc:  # noqa: BLE001
        recorder = Recorder()
        state = AcceptanceState()
        recorder.add("global acceptance", "fatal setup error", "failed", str(exc))
    print_summary(recorder, state)
    return 1 if recorder.failed() else 0


if __name__ == "__main__":
    raise SystemExit(main())
