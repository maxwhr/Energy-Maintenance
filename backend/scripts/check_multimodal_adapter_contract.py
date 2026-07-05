from __future__ import annotations

import json
import os
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
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402
from seed_external_api_providers import main as seed_external_api_providers  # noqa: E402


API_BASE_URL = os.getenv("MULTIMODAL_ADAPTER_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("MULTIMODAL_ADAPTER_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22E_{RUN_ID}"
TEST_PASSWORD = os.getenv("MULTIMODAL_ADAPTER_TEST_PASSWORD", "Task22E_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("MULTIMODAL_ADAPTER_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("MULTIMODAL_ADAPTER_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class MultimodalAdapterContractError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    engineer_token: str | None = None
    expert_token: str | None = None
    viewer_token: str | None = None
    media_id: str | None = None
    dry_trace_id: str | None = None
    mock_trace_id: str | None = None
    analysis_id: str | None = None
    ocr_result_id: str | None = None
    agent_run_id: str | None = None
    zip_snapshot: dict[str, int] = field(default_factory=dict)
    results: list[dict[str, str]] = field(default_factory=list)


def record(state: State, name: str, status: str, notes: str = "") -> None:
    state.results.append({"name": name, "status": status, "notes": notes})
    print(f"[{status}] {name}: {notes}")


def delivery_zip_snapshot() -> dict[str, int]:
    delivery_dir = ROOT_DIR / "delivery"
    if not delivery_dir.exists():
        return {}
    return {str(path.relative_to(ROOT_DIR)): path.stat().st_mtime_ns for path in delivery_dir.rglob("*.zip")}


def request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    url = path if path.startswith("http") else f"{API_BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {"code": exc.code, "message": exc.reason, "data": None}
        except json.JSONDecodeError:
            body = {"code": exc.code, "message": raw[:300], "data": None}
        return exc.code, body


def api_data(label: str, status: int, response: dict[str, Any]) -> Any:
    if status >= 400 or response.get("code") not in (0, 200):
        raise MultimodalAdapterContractError(
            f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}"
        )
    return response.get("data")


def expect_forbidden(label: str, status: int, response: dict[str, Any]) -> None:
    code = response.get("code")
    if status in (401, 403) or (isinstance(code, int) and code not in (0, 200)):
        return
    raise MultimodalAdapterContractError(f"{label} should be forbidden, got http={status}, code={code}")


def ensure_seed_and_users(state: State) -> None:
    first = seed_external_api_providers()
    second = seed_external_api_providers()
    if first != 0 or second != 0:
        raise MultimodalAdapterContractError("seed_external_api_providers.py did not succeed twice")
    state.admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        cga.ensure_user(state.admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", token)
    record(state, "seed and login admin/engineer/expert/viewer", "passed", "tokens acquired")


def upload_media(state: State) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} PV inverter alarm screen adapter contract"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
        ("fault_type", "alarm_code_query"),
        ("alarm_code", "MOCK-ALM-22E"),
    ]
    body, content_type = cga.multipart_body(fields, "file", f"{MARKER}_alarm.png", cga.SAMPLE_PNG, "image/png")
    status, response = cga.request_json(
        "POST",
        "/media/upload",
        token=state.engineer_token,
        body=body,
        content_type=content_type,
        timeout=60,
    )
    media = api_data("media upload", status, response)
    state.media_id = str(media.get("media_id") or media.get("id"))
    if not state.media_id:
        raise MultimodalAdapterContractError("media upload did not return media_id")
    record(state, "Task22E media upload", "passed", state.media_id)


def check_status_and_dry_run(state: State) -> None:
    status, response = request_json("GET", "/external-apis/status", token=state.viewer_token)
    gateway_status = api_data("external API status", status, response)
    provider_codes = {item["provider_code"] for item in gateway_status.get("providers", [])}
    if "mimo_2_5" not in provider_codes:
        raise MultimodalAdapterContractError("mimo_2_5 provider missing")
    if gateway_status.get("real_external_calls_enabled") is not False:
        raise MultimodalAdapterContractError("real external calls must remain disabled")
    record(state, "provider status contains mimo_2_5", "passed", "real_external_calls_enabled=false")

    payload = {
        "tool_name": "media_mimo_analysis",
        "capability": "fault_scene_analysis",
        "input_summary": {
            "marker": MARKER,
            "media_ids": [state.media_id],
            "image_base64": "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=",
            "Authorization": "Bearer SHOULD_NOT_APPEAR",
            "file_path": "C:\\secret\\should_not_appear.png",
            "question": "Check Huawei SUN2000 alarm screen.",
        },
    }
    status, response = request_json("POST", "/external-apis/dry-run", token=state.engineer_token, payload=payload)
    data = api_data("engineer dry-run", status, response)
    state.dry_trace_id = data.get("trace_id")
    if data.get("external_api_called") is not False:
        raise MultimodalAdapterContractError("dry-run attempted external API")
    if data.get("status") not in {"blocked", "not_configured", "would_call"}:
        raise MultimodalAdapterContractError(f"unexpected dry-run status: {data.get('status')}")
    record(state, "dry-run mimo fault_scene_analysis", "passed", data.get("status", ""))

    status, response = request_json("GET", f"/external-apis/logs/{state.dry_trace_id}", token=state.viewer_token)
    log = api_data("dry-run log", status, response)
    raw = json.dumps(log, ensure_ascii=False)
    forbidden = ["SHOULD_NOT_APPEAR", "should_not_appear.png", "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="]
    leaked = [item for item in forbidden if item in raw]
    if leaked:
        raise MultimodalAdapterContractError(f"dry-run log leaked sensitive data: {leaked}")
    record(state, "dry-run log sanitized", "passed", state.dry_trace_id or "")


def check_mock_run_endpoint_and_permissions(state: State) -> None:
    payload = {
        "provider_code": "mimo_2_5",
        "capability": "fault_scene_analysis",
        "input_summary": {"marker": MARKER, "media_ids": [state.media_id], "image_count": 1},
    }
    status, response = request_json("POST", "/external-apis/mock-run", token=state.expert_token, payload=payload)
    data = api_data("expert mock-run", status, response)
    state.mock_trace_id = data.get("trace_id")
    if data.get("status") != "mocked" or data.get("external_api_called") is not False:
        raise MultimodalAdapterContractError(f"mock-run did not return mocked/no-call: {data}")
    if (data.get("normalized_result") or {}).get("mocked") is not True:
        raise MultimodalAdapterContractError("mock-run normalized_result missing mocked=true")
    record(state, "mock-run fault_scene_analysis", "passed", state.mock_trace_id or "")

    status, response = request_json("POST", "/external-apis/mock-run", token=state.viewer_token, payload=payload)
    expect_forbidden("viewer mock-run", status, response)
    record(state, "viewer mock-run forbidden", "passed", f"http={status}")


def check_multimodal_mock_persistence(state: State) -> None:
    if not state.media_id:
        raise MultimodalAdapterContractError("media_id missing")
    analysis_payload = {
        "job_type": "multimodal_analysis",
        "provider_code": "mimo_2_5",
        "capability": "fault_scene_analysis",
        "analysis_type": "fault_scene",
        "dry_run": False,
        "mock_run": True,
        "input_summary": {"marker": MARKER, "image_count": 1},
    }
    status, response = request_json(
        "POST",
        f"/multimodal/media/{state.media_id}/jobs",
        token=state.expert_token,
        payload=analysis_payload,
    )
    job = api_data("mock multimodal job", status, response)
    if job.get("status") != "succeeded" or (job.get("result_summary_json") or {}).get("mocked") is not True:
        raise MultimodalAdapterContractError(f"mock multimodal job was not persisted as mocked success: {job}")
    state.analysis_id = (job.get("result_summary_json") or {}).get("persisted_result_id")
    record(state, "mock multimodal job persisted", "passed", state.analysis_id or "")

    ocr_payload = {
        "job_type": "ocr",
        "provider_code": "tesseract_ocr",
        "capability": "ocr",
        "dry_run": False,
        "mock_run": True,
        "input_summary": {"marker": MARKER, "image_count": 1},
    }
    status, response = request_json(
        "POST",
        f"/multimodal/media/{state.media_id}/jobs",
        token=state.expert_token,
        payload=ocr_payload,
    )
    job = api_data("mock OCR job", status, response)
    if job.get("status") != "succeeded" or (job.get("result_summary_json") or {}).get("mocked") is not True:
        raise MultimodalAdapterContractError(f"mock OCR job was not persisted as mocked success: {job}")
    state.ocr_result_id = (job.get("result_summary_json") or {}).get("persisted_result_id")
    record(state, "mock OCR job persisted", "passed", state.ocr_result_id or "")

    status, response = request_json("GET", f"/multimodal/media/{state.media_id}/summary", token=state.viewer_token)
    summary = api_data("media summary", status, response)
    if not summary.get("analyses") or not summary.get("ocr_results"):
        raise MultimodalAdapterContractError("summary did not include mocked analysis and OCR result")
    raw = json.dumps(summary, ensure_ascii=False)
    if '"mocked": true' not in raw:
        raise MultimodalAdapterContractError("summary did not preserve mocked=true marker")
    record(state, "summary includes mocked analysis/OCR", "passed", state.media_id)

    status, response = request_json(
        "POST",
        f"/multimodal/media/{state.media_id}/jobs",
        token=state.viewer_token,
        payload=analysis_payload,
    )
    expect_forbidden("viewer create mock job", status, response)
    record(state, "viewer create job forbidden", "passed", f"http={status}")


def check_agent_tools_read_mock_results(state: State) -> None:
    payload = {
        "agent_code": "multimodal_evidence_agent",
        "input_text": "Use mocked multimodal adapter evidence for Huawei SUN2000 inverter alarm screen.",
        "media_ids": [state.media_id],
        "tools": ["media_mimo_analysis", "media_ocr"],
        "context": {
            "agent_code": "multimodal_evidence_agent",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
        },
        "tool_inputs": {
            "media_mimo_analysis": {"mock_run": True},
            "media_ocr": {"mock_run": True},
        },
        "dry_run": True,
    }
    status, response = request_json("POST", "/agents/runs", token=state.expert_token, payload=payload, timeout=60)
    run = api_data("agent run", status, response)
    state.agent_run_id = run["run_id"]
    status, response = request_json("GET", f"/agents/runs/{state.agent_run_id}", token=state.expert_token)
    detail = api_data("agent detail", status, response)
    calls = {item["tool_name"]: item for item in detail.get("tool_calls", [])}
    mimo_output = (calls.get("media_mimo_analysis") or {}).get("output_json") or {}
    mimo_data = mimo_output.get("data") or {}
    if mimo_output.get("status") not in {"succeeded", "waiting_approval"} or not mimo_data.get("analyses"):
        raise MultimodalAdapterContractError("media_mimo_analysis did not read mocked analysis")
    if mimo_data.get("source") not in {"mocked_analysis", "accepted_analysis"}:
        raise MultimodalAdapterContractError(f"unexpected mimo source: {mimo_data.get('source')}")
    ocr_output = (calls.get("media_ocr") or {}).get("output_json") or {}
    ocr_data = ocr_output.get("data") or {}
    if ocr_output.get("status") != "succeeded" or not ocr_data.get("ocr_context"):
        raise MultimodalAdapterContractError("media_ocr did not read mocked OCR")
    record(state, "agent tools read mocked results", "passed", state.agent_run_id)


def check_logs_and_no_package(state: State) -> None:
    status, response = request_json("GET", "/external-apis/logs?page=1&page_size=20", token=state.viewer_token)
    logs = api_data("external API logs", status, response)
    items = logs.get("items", [])
    if not items:
        raise MultimodalAdapterContractError("external API logs are empty")
    raw = json.dumps(items, ensure_ascii=False)
    forbidden = ["SHOULD_NOT_APPEAR", "should_not_appear.png", "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=", "Bearer "]
    leaked = [item for item in forbidden if item in raw]
    if leaked:
        raise MultimodalAdapterContractError(f"external API logs leaked sensitive data: {leaked}")
    after = delivery_zip_snapshot()
    if after != state.zip_snapshot:
        raise MultimodalAdapterContractError("delivery zip snapshot changed during Task 22E check")
    record(state, "logs sanitized and no package generated", "passed", f"logs={len(items)} zip_count={len(after)}")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed_and_users(state)
        upload_media(state)
        check_status_and_dry_run(state)
        check_mock_run_endpoint_and_permissions(state)
        check_multimodal_mock_persistence(state)
        check_agent_tools_read_mock_results(state)
        check_logs_and_no_package(state)
    except Exception as exc:  # noqa: BLE001
        record(state, "multimodal adapter contract", "failed", str(exc))
        print(json.dumps({"status": "failed", "results": state.results}, ensure_ascii=False, indent=2))
        return 1
    print(
        "multimodal_adapter_contract_result "
        f"checks={len(state.results)} media_id={state.media_id} "
        f"analysis_id={state.analysis_id} ocr_result_id={state.ocr_result_id} run_id={state.agent_run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
