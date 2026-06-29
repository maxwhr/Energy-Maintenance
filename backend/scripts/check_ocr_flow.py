from __future__ import annotations

import base64
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request


BASE_URL = os.getenv("OCR_FLOW_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
SAMPLE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass(slots=True)
class FlowState:
    mode: str = "failed"
    notes: list[str] = field(default_factory=list)
    media_id: str | None = None
    ocr_status: str | None = None
    retrieval_trace_id: str | None = None
    diagnosis_trace_id: str | None = None


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str = "application/json",
    timeout: int = 60,
) -> tuple[int, dict[str, Any]]:
    data = body
    headers = {"Content-Type": content_type}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {"code": exc.code, "message": exc.reason, "data": None}
        except json.JSONDecodeError:
            parsed = {"code": exc.code, "message": raw[:500], "data": None}
        return exc.code, parsed


def api_data(label: str, status: int, response: dict[str, Any]) -> Any:
    if status >= 400 or response.get("code") not in (0, 200):
        raise AssertionError(f"{label} failed: http={status}, message={response.get('message')}")
    data = response.get("data")
    if data is None:
        raise AssertionError(f"{label} returned empty data")
    print(f"[passed] {label}")
    return data


def login(username: str, password: str) -> str:
    status, response = request_json(
        "POST",
        f"{BASE_URL}/auth/login",
        payload={"username": username, "password": password},
    )
    data = api_data(f"login {username}", status, response)
    token = data.get("access_token")
    if not token:
        raise AssertionError(f"login {username} did not return access_token")
    return token


def try_login(username: str, password: str) -> str | None:
    try:
        return login(username, password)
    except Exception as exc:
        print(f"[info] viewer login skipped: {exc}")
        return None


def multipart_upload_body() -> tuple[bytes, str]:
    boundary = f"----EnergyMaintenanceOCR{uuid.uuid4().hex}"
    fields = [
        ("media_type", "fault_image"),
        ("device_type", "pv_inverter"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("description", "OCR flow verification sample image. Machine text recognition only."),
    ]
    parts: list[bytes] = []
    for name, value in fields:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        b'Content-Disposition: form-data; name="file"; filename="ocr_flow_sample.png"\r\n'
        b"Content-Type: image/png\r\n\r\n"
    )
    parts.append(SAMPLE_PNG)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def upload_sample_media(token: str) -> str:
    body, content_type = multipart_upload_body()
    status, response = request_json(
        "POST",
        f"{BASE_URL}/media/upload",
        token=token,
        body=body,
        content_type=content_type,
        timeout=90,
    )
    data = api_data("upload sample media", status, response)
    media_id = data.get("media_id")
    if not media_id:
        raise AssertionError("media upload did not return media_id")
    return str(media_id)


def assert_viewer_blocked(viewer_token: str | None, media_id: str | None, state: FlowState) -> None:
    if not viewer_token:
        state.notes.append("viewer account was not available; viewer OCR permission probe skipped")
        return
    probe_id = media_id or str(uuid.uuid4())
    status, response = request_json("POST", f"{BASE_URL}/media/{probe_id}/ocr", token=viewer_token)
    if status != 403 and response.get("code") not in (40301, 40302):
        raise AssertionError(f"viewer OCR trigger was not blocked: http={status}, response={response}")
    print("[passed] viewer OCR trigger blocked")
    state.notes.append("viewer OCR trigger blocked")


def run_available_flow(admin_token: str, state: FlowState) -> None:
    media_id = upload_sample_media(admin_token)
    state.media_id = media_id
    status, response = request_json("POST", f"{BASE_URL}/media/{media_id}/ocr", token=admin_token, timeout=90)
    ocr_data = api_data("run media OCR", status, response)
    state.ocr_status = str(ocr_data.get("status"))
    if state.ocr_status not in {"processed", "failed"}:
        raise AssertionError(f"OCR returned unexpected status: {ocr_data}")
    print(f"[info] media OCR status={state.ocr_status}")

    status, response = request_json("GET", f"{BASE_URL}/media/{media_id}/ocr", token=admin_token)
    detail = api_data("get media OCR", status, response)
    if detail.get("status") != state.ocr_status:
        raise AssertionError("GET media OCR status does not match POST result")

    if state.ocr_status != "processed":
        state.mode = "blocked"
        state.notes.append("OCR engine was available, but sample image did not produce text")
        return

    retrieval_payload = {
        "query": "Use OCR context for Huawei SUN2000 alarm inspection",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "media_ids": [media_id],
        "use_ocr_text": True,
        "top_k": 3,
        "enable_model_enhancement": False,
    }
    status, response = request_json("POST", f"{BASE_URL}/retrieval/query", token=admin_token, payload=retrieval_payload)
    retrieval = api_data("retrieval use_ocr_text", status, response)
    state.retrieval_trace_id = retrieval.get("trace_id")
    if not retrieval.get("ocr_context"):
        raise AssertionError("retrieval response did not include ocr_context")

    diagnosis_payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "alarm_code_query",
        "fault_description": "OCR flow verification with selected media.",
        "media_ids": [media_id],
        "use_ocr_text": True,
        "enable_model_enhancement": False,
    }
    status, response = request_json("POST", f"{BASE_URL}/diagnosis/analyze", token=admin_token, payload=diagnosis_payload)
    diagnosis = api_data("diagnosis use_ocr_text", status, response)
    state.diagnosis_trace_id = diagnosis.get("trace_id")
    if not diagnosis.get("ocr_context"):
        raise AssertionError("diagnosis response did not include ocr_context")
    state.mode = "passed"


def run() -> FlowState:
    state = FlowState()
    admin_username = os.getenv("OCR_FLOW_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
    admin_password = os.getenv("OCR_FLOW_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
    viewer_username = os.getenv("OCR_FLOW_VIEWER_USERNAME", "viewer")
    viewer_password = os.getenv("OCR_FLOW_VIEWER_PASSWORD", "viewer123456")
    admin_token = login(admin_username, admin_password)
    viewer_token = try_login(viewer_username, viewer_password)

    status, response = request_json("GET", f"{BASE_URL}/media/ocr/status", token=admin_token)
    ocr_status = api_data("media OCR status", status, response)
    state.ocr_status = str(ocr_status.get("status"))
    print(json.dumps({"ocr_status": ocr_status}, ensure_ascii=False, indent=2))

    if state.ocr_status in {"disabled", "not_configured"}:
        state.mode = "blocked"
        if state.ocr_status == "not_configured" and not ocr_status.get("error_summary"):
            raise AssertionError("not_configured OCR status should include error_summary")
        assert_viewer_blocked(viewer_token, None, state)
        state.notes.append(f"OCR status is {state.ocr_status}; real recognition was not attempted")
        return state

    if state.ocr_status != "available":
        raise AssertionError(f"unexpected OCR status: {ocr_status}")

    run_available_flow(admin_token, state)
    assert_viewer_blocked(viewer_token, state.media_id, state)
    return state


def main() -> int:
    state = run()
    print(
        json.dumps(
            {
                "result": {
                    "mode": state.mode,
                    "media_id": state.media_id,
                    "ocr_status": state.ocr_status,
                    "retrieval_trace_id": state.retrieval_trace_id,
                    "diagnosis_trace_id": state.diagnosis_trace_id,
                    "notes": state.notes,
                }
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
