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


API_BASE_URL = os.getenv("EXTERNAL_API_GATEWAY_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("EXTERNAL_API_GATEWAY_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22C_{RUN_ID}"
TEST_PASSWORD = os.getenv("EXTERNAL_API_GATEWAY_TEST_PASSWORD", "Task22C_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("EXTERNAL_API_GATEWAY_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("EXTERNAL_API_GATEWAY_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class ExternalApiGatewayCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    engineer_token: str | None = None
    viewer_token: str | None = None
    dry_run_trace_id: str | None = None
    run_id: str | None = None
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
        raise ExternalApiGatewayCheckError(
            f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}"
        )
    return response.get("data")


def expect_forbidden(label: str, status: int, response: dict[str, Any]) -> None:
    code = response.get("code")
    if status in (401, 403) or (isinstance(code, int) and code not in (0, 200)):
        return
    raise ExternalApiGatewayCheckError(f"{label} should be forbidden, got http={status}, code={code}")


def ensure_seed(state: State) -> None:
    first = seed_external_api_providers()
    second = seed_external_api_providers()
    if first != 0 or second != 0:
        raise ExternalApiGatewayCheckError("seed_external_api_providers.py did not return success twice")
    record(state, "seed_external_api_providers twice", "passed", "idempotent=true")


def ensure_users(state: State) -> None:
    admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    state.admin_token = admin_token
    for role in ("engineer", "viewer"):
        username = f"{MARKER}_{role}"
        cga.ensure_user(admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", token)
    record(state, "login admin/engineer/viewer", "passed", "tokens acquired")


def check_providers(state: State) -> None:
    expected = {
        "mimo_2_5",
        "cloud_openai",
        "cloud_openai_vision",
        "local_llama_cpp",
        "tesseract_ocr",
        "custom_ocr_api",
        "safety_rule_engine",
    }
    status, response = request_json("GET", "/external-apis/providers", token=state.viewer_token)
    providers = api_data("GET providers", status, response)
    codes = {item["provider_code"] for item in providers}
    missing = expected - codes
    if missing:
        raise ExternalApiGatewayCheckError(f"missing providers: {sorted(missing)}")
    raw = json.dumps(providers, ensure_ascii=False).lower()
    forbidden_fragments = ["authorization", "bearer ", "sk-", "real_api_key", "secret_key_value"]
    leaked = [item for item in forbidden_fragments if item in raw]
    if leaked:
        raise ExternalApiGatewayCheckError(f"provider response leaked forbidden fragments: {leaked}")
    record(state, "GET /external-apis/providers", "passed", f"providers={len(providers)}")

    status, response = request_json("GET", "/external-apis/providers/mimo_2_5", token=state.viewer_token)
    api_data("GET provider detail", status, response)
    record(state, "GET /external-apis/providers/{provider_code}", "passed", "mimo_2_5")


def check_routes_and_status(state: State) -> None:
    status, response = request_json("GET", "/external-apis/routes", token=state.viewer_token)
    routes = api_data("GET routes", status, response)
    route_codes = {item["route_code"] for item in routes}
    expected = {"agent_multimodal_mimo", "agent_media_ocr", "agent_model_chat", "agent_safety_review"}
    missing = expected - route_codes
    if missing:
        raise ExternalApiGatewayCheckError(f"missing routes: {sorted(missing)}")
    record(state, "GET /external-apis/routes", "passed", f"routes={len(routes)}")

    status, response = request_json("GET", "/external-apis/status", token=state.viewer_token)
    gateway_status = api_data("GET status", status, response)
    if gateway_status.get("real_external_calls_enabled") is not False:
        raise ExternalApiGatewayCheckError("external API gateway must not enable real external calls in Task 22C")
    record(state, "GET /external-apis/status", "passed", "real_external_calls_enabled=false")


def check_provider_admin_check(state: State) -> None:
    status, response = request_json("POST", "/external-apis/providers/mimo_2_5/check", token=state.admin_token)
    data = api_data("admin check provider", status, response)
    if data.get("external_api_called") is not False:
        raise ExternalApiGatewayCheckError("admin provider check attempted external API")
    if data.get("status") not in {"disabled", "blocked", "not_configured"}:
        raise ExternalApiGatewayCheckError(f"unexpected provider check status: {data.get('status')}")
    record(state, "POST /external-apis/providers/mimo_2_5/check", "passed", data.get("status", ""))


def check_dry_run_and_logs(state: State) -> None:
    payload = {
        "tool_name": "media_mimo_analysis",
        "capability": "fault_scene_analysis",
        "input_summary": {
            "image_base64": "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=",
            "Authorization": "Bearer SHOULD_NOT_BE_LOGGED",
            "file_path": "C:\\secret\\pv_inverter_alarm.png",
            "question": "Inspect Huawei SUN2000 alarm screen.",
        },
    }
    status, response = request_json("POST", "/external-apis/dry-run", token=state.engineer_token, payload=payload)
    data = api_data("engineer dry-run", status, response)
    state.dry_run_trace_id = data.get("trace_id")
    if data.get("external_api_called") is not False:
        raise ExternalApiGatewayCheckError("dry-run attempted external API")
    if data.get("status") not in {"blocked", "not_configured"} and not data.get("would_call"):
        raise ExternalApiGatewayCheckError(f"unexpected dry-run status: {data.get('status')}")
    record(state, "POST /external-apis/dry-run as engineer", "passed", data.get("status", ""))

    status, response = request_json("POST", "/external-apis/dry-run", token=state.viewer_token, payload=payload)
    expect_forbidden("viewer dry-run", status, response)
    record(state, "viewer dry-run forbidden", "passed", f"http={status}")

    status, response = request_json("GET", "/external-apis/logs?page=1&page_size=5", token=state.viewer_token)
    logs = api_data("GET logs", status, response)
    items = logs.get("items", [])
    if not items:
        raise ExternalApiGatewayCheckError("external_api_call_logs is empty after dry-run")
    raw = json.dumps(items, ensure_ascii=False)
    forbidden = ["SHOULD_NOT_BE_LOGGED", "pv_inverter_alarm.png", "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="]
    leaked = [item for item in forbidden if item in raw]
    if leaked:
        raise ExternalApiGatewayCheckError(f"external_api_call_logs leaked unsanitized data: {leaked}")
    record(state, "GET /external-apis/logs sanitized", "passed", f"items={len(items)}")

    if not state.dry_run_trace_id:
        raise ExternalApiGatewayCheckError("dry-run trace_id missing")
    status, response = request_json("GET", f"/external-apis/logs/{state.dry_run_trace_id}", token=state.viewer_token)
    api_data("GET log detail", status, response)
    record(state, "GET /external-apis/logs/{trace_id}", "passed", state.dry_run_trace_id)

    status, response = request_json("GET", "/external-apis/health-checks?page=1&page_size=5", token=state.viewer_token)
    api_data("GET health checks", status, response)
    record(state, "GET /external-apis/health-checks", "passed", "readable")


def check_agent_tool_integration(state: State) -> None:
    payload = {
        "agent_code": "retrieval_qa_agent",
        "input_text": "Check reserved external provider route for PV inverter evidence analysis.",
        "tools": ["media_mimo_analysis", "media_ocr", "model_gateway_chat"],
        "context": {
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
        },
        "tool_inputs": {
            "model_gateway_chat": {"prompt": "Summarize provider gateway dry-run status.", "task_type": "general"}
        },
        "dry_run": True,
    }
    status, response = request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload, timeout=60)
    run = api_data("agent run with external API tools", status, response)
    state.run_id = run["run_id"]

    status, response = request_json("GET", f"/agents/runs/{state.run_id}", token=state.engineer_token)
    detail = api_data("agent detail", status, response)
    calls = {item["tool_name"]: item for item in detail.get("tool_calls", [])}
    for name in ("media_mimo_analysis", "media_ocr", "model_gateway_chat"):
        if name not in calls:
            raise ExternalApiGatewayCheckError(f"missing agent tool call: {name}")

    mimo_output = calls["media_mimo_analysis"].get("output_json") or {}
    mimo_gateway = ((mimo_output.get("data") or {}).get("external_api_gateway") or {})
    if mimo_output.get("status") != "blocked" or mimo_gateway.get("provider_code") != "mimo_2_5":
        raise ExternalApiGatewayCheckError("media_mimo_analysis did not read mimo_2_5 provider route")

    ocr_output = calls["media_ocr"].get("output_json") or {}
    ocr_gateway = ((ocr_output.get("data") or {}).get("external_api_gateway") or {})
    if ocr_output.get("status") not in {"blocked", "succeeded"}:
        raise ExternalApiGatewayCheckError(f"unexpected media_ocr status: {ocr_output.get('status')}")
    if ocr_output.get("status") == "blocked" and ocr_gateway.get("provider_code") != "tesseract_ocr":
        raise ExternalApiGatewayCheckError("media_ocr did not read tesseract_ocr provider route")

    model_output = calls["model_gateway_chat"].get("output_json") or {}
    model_data = model_output.get("data") or {}
    model_gateway = model_data.get("external_api_gateway") or {}
    raw = json.dumps(model_data, ensure_ascii=False).lower()
    if "api_key" in raw and "***masked***" not in raw:
        raise ExternalApiGatewayCheckError("model_gateway_chat output may expose API key material")
    if model_gateway.get("provider_code") != "cloud_openai":
        raise ExternalApiGatewayCheckError("model_gateway_chat did not record cloud_openai route status")
    record(state, "agent tool provider route integration", "passed", state.run_id)


def check_no_delivery_zip_generated(state: State) -> None:
    after = delivery_zip_snapshot()
    if after != state.zip_snapshot:
        raise ExternalApiGatewayCheckError("delivery zip snapshot changed during Task 22C gateway check")
    record(state, "no delivery zip generated", "passed", f"zip_count={len(after)}")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed(state)
        ensure_users(state)
        check_providers(state)
        check_routes_and_status(state)
        check_provider_admin_check(state)
        check_dry_run_and_logs(state)
        check_agent_tool_integration(state)
        check_no_delivery_zip_generated(state)
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] external API gateway flow: {exc}")
        return 1
    print(
        "external_api_gateway_flow_result "
        f"checks={len(state.results)} trace_id={state.dry_run_trace_id} run_id={state.run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
