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
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402


API_BASE_URL = os.getenv("AGENT_TOOLS_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("AGENT_TOOLS_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22B_{RUN_ID}"
TEST_PASSWORD = os.getenv("AGENT_TOOLS_TEST_PASSWORD", "Task22B_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("AGENT_TOOLS_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("AGENT_TOOLS_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class AgentBusinessToolsCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    expert_token: str | None = None
    engineer_token: str | None = None
    viewer_token: str | None = None
    device_id: str | None = None
    run_id: str | None = None
    approval_id: str | None = None
    results: list[dict[str, str]] = field(default_factory=list)


def record(state: State, name: str, status: str, notes: str = "") -> None:
    state.results.append({"name": name, "status": status, "notes": notes})
    print(f"[{status}] {name}: {notes}")


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
        raise AgentBusinessToolsCheckError(
            f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}"
        )
    return response.get("data")


def expect_forbidden(label: str, status: int, response: dict[str, Any]) -> None:
    code = response.get("code")
    if status in (401, 403) or (isinstance(code, int) and code not in (0, 200)):
        return
    raise AgentBusinessToolsCheckError(f"{label} should be forbidden, got http={status}, code={code}")


def ensure_seed() -> None:
    from seed_agent_runtime import main as seed_main

    first = seed_main()
    second = seed_main()
    if first != 0 or second != 0:
        raise AgentBusinessToolsCheckError("seed_agent_runtime.py did not return success twice")


def ensure_users(state: State) -> None:
    admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    state.admin_token = admin_token
    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        cga.ensure_user(admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", token)


def check_tool_registry(state: State) -> None:
    status, response = request_json("GET", "/agents/tools", token=state.viewer_token)
    tools = api_data("tools", status, response)
    by_name = {item["tool_name"]: item for item in tools}
    expected = {
        "knowledge_search",
        "kg_business_context",
        "device_lookup",
        "device_history",
        "media_lookup",
        "media_ocr",
        "media_mimo_analysis",
        "diagnosis_rule_engine",
        "sop_generator",
        "task_draft_creator",
        "knowledge_contribution_draft_creator",
        "record_center_lookup",
        "safety_guard",
        "model_gateway_chat",
        "correction_submitter",
        "human_approval",
    }
    missing = expected - set(by_name)
    if missing:
        raise AgentBusinessToolsCheckError(f"missing agent tools: {sorted(missing)}")
    if by_name["media_mimo_analysis"]["enabled"] is not False:
        raise AgentBusinessToolsCheckError("media_mimo_analysis must remain disabled/blocked")
    record(state, "agent tool registry", "passed", f"tools={len(tools)} expected={len(expected)}")


def ensure_device_fixture(state: State) -> None:
    payload = {
        "device_code": f"{MARKER}_PV_INV_01",
        "device_name": f"{MARKER} Huawei SUN2000 inverter",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-50KTL-M3",
        "device_type": "pv_inverter",
        "station_name": "Task22B Verification Station",
        "location": "Task22B test area",
        "status": "normal",
        "description": "Task22B disposable verification device for agent business tools.",
    }
    status, response = request_json("POST", "/devices", token=state.engineer_token, payload=payload)
    device = api_data("create device fixture", status, response)
    state.device_id = device["id"]
    record(state, "device fixture", "passed", state.device_id)

    record_payload = {
        "fault_type": "low_insulation_resistance",
        "alarm_code": "ALM-2062",
        "fault_description": "Task22B insulation alarm verification history.",
        "root_cause": "Connector moisture and string insulation degradation were suspected.",
        "repair_action": "Checked strings, dried connector, and verified insulation resistance.",
        "verification_result": "Alarm cleared after inspection and re-test.",
        "is_recurrent": False,
        "metadata_json": {"marker": MARKER, "purpose": "agent_business_tools_device_history"},
    }
    status, response = request_json(
        "POST",
        f"/devices/{state.device_id}/maintenance-records",
        token=state.engineer_token,
        payload=record_payload,
    )
    api_data("create device history fixture", status, response)
    record(state, "device history fixture", "passed", "maintenance record created")


def check_full_tool_run(state: State) -> None:
    if not state.device_id:
        raise AgentBusinessToolsCheckError("device fixture was not created")
    tools = [
        "knowledge_search",
        "kg_business_context",
        "device_lookup",
        "device_history",
        "media_lookup",
        "media_ocr",
        "media_mimo_analysis",
        "diagnosis_rule_engine",
        "sop_generator",
        "task_draft_creator",
        "knowledge_contribution_draft_creator",
        "record_center_lookup",
        "safety_guard",
        "model_gateway_chat",
        "correction_submitter",
        "human_approval",
    ]
    payload = {
        "agent_code": "task_orchestration_agent",
        "input_text": "Huawei SUN2000 inverter reports insulation alarm. Please retrieve knowledge, check safety, draft SOP and task.",
        "device_id": state.device_id,
        "tools": tools,
        "context": {
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "fault_type": "low_insulation_resistance",
            "alarm_code": "ALM-2062",
        },
        "tool_inputs": {
            "record_center_lookup": {"record_type": "all", "page_size": 5},
            "model_gateway_chat": {"task_type": "general"},
            "task_draft_creator": {"priority": "high", "assignee": "field_engineer"},
        },
        "dry_run": True,
    }
    status, response = request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload, timeout=60)
    run = api_data("create full tool run", status, response)
    state.run_id = run["run_id"]
    if run.get("status") != "waiting_approval":
        raise AgentBusinessToolsCheckError(f"full tool run should wait for approval, got {run.get('status')}")
    record(state, "POST /api/agents/runs with business tools", "passed", state.run_id)

    status, response = request_json("GET", f"/agents/runs/{state.run_id}", token=state.engineer_token)
    detail = api_data("run detail", status, response)
    calls = detail.get("tool_calls", [])
    artifacts = detail.get("artifacts", [])
    approvals = detail.get("approvals", [])
    statuses = {call["tool_name"]: call["status"] for call in calls}
    for name in tools:
        if name not in statuses:
            raise AgentBusinessToolsCheckError(f"tool call missing for {name}")
    if statuses["media_mimo_analysis"] != "blocked":
        raise AgentBusinessToolsCheckError("media_mimo_analysis should be blocked")
    if statuses["media_ocr"] not in {"blocked", "succeeded"}:
        raise AgentBusinessToolsCheckError(f"media_ocr should be blocked or succeeded, got {statuses['media_ocr']}")
    if statuses["task_draft_creator"] != "waiting_approval":
        raise AgentBusinessToolsCheckError("task_draft_creator should be waiting_approval")
    if statuses["knowledge_contribution_draft_creator"] != "waiting_approval":
        raise AgentBusinessToolsCheckError("knowledge_contribution_draft_creator should be waiting_approval")
    succeeded_count = sum(1 for status_value in statuses.values() if status_value == "succeeded")
    if succeeded_count < 10:
        raise AgentBusinessToolsCheckError(f"expected at least 10 succeeded tools, got {succeeded_count}")
    by_tool = {call["tool_name"]: call for call in calls}
    knowledge_output = by_tool["knowledge_search"].get("output_json") or {}
    knowledge_data = knowledge_output.get("data") or {}
    if "trace_id" not in knowledge_data or "retrieved_chunks" not in knowledge_data:
        raise AgentBusinessToolsCheckError("knowledge_search output must include trace_id and retrieved_chunks")
    kg_data = (by_tool["kg_business_context"].get("output_json") or {}).get("data") or {}
    if "summary" not in kg_data:
        raise AgentBusinessToolsCheckError("kg_business_context output must include summary")
    diagnosis_data = (by_tool["diagnosis_rule_engine"].get("output_json") or {}).get("data") or {}
    if not diagnosis_data.get("trace_id") or not diagnosis_data.get("diagnosis_summary"):
        raise AgentBusinessToolsCheckError("diagnosis_rule_engine output must include trace_id and diagnosis_summary")
    sop_data = (by_tool["sop_generator"].get("output_json") or {}).get("data") or {}
    if not sop_data.get("steps"):
        raise AgentBusinessToolsCheckError("sop_generator output must include generated steps")
    task_draft_data = (by_tool["task_draft_creator"].get("output_json") or {}).get("data") or {}
    if (task_draft_data.get("task_draft") or {}).get("formal_task_created") is not False:
        raise AgentBusinessToolsCheckError("task_draft_creator must not create a formal task")
    contribution_draft_data = (
        (by_tool["knowledge_contribution_draft_creator"].get("output_json") or {}).get("data") or {}
    )
    if (contribution_draft_data.get("knowledge_contribution_draft") or {}).get(
        "formal_contribution_created"
    ) is not False:
        raise AgentBusinessToolsCheckError(
            "knowledge_contribution_draft_creator must not create a formal contribution"
        )
    if not any(item.get("artifact_type") == "task_draft" for item in artifacts):
        raise AgentBusinessToolsCheckError("task_draft artifact missing")
    if not any(item.get("artifact_type") == "knowledge_contribution_draft" for item in artifacts):
        raise AgentBusinessToolsCheckError("knowledge_contribution_draft artifact missing")
    if not approvals:
        raise AgentBusinessToolsCheckError("approval record missing")
    state.approval_id = approvals[0]["id"]
    record(
        state,
        "business tool calls/artifacts/approval",
        "passed",
        f"calls={len(calls)} succeeded={succeeded_count} artifacts={len(artifacts)} approval={state.approval_id}",
    )


def check_manual_execute_endpoint(state: State) -> None:
    if not state.run_id:
        raise AgentBusinessToolsCheckError("run_id is missing")
    payload = {"tool_name": "safety_guard", "input": {"fault_type": "dc_abnormal"}, "dry_run": True}
    status, response = request_json(
        "POST",
        f"/agents/runs/{state.run_id}/execute-tool",
        token=state.engineer_token,
        payload=payload,
    )
    result = api_data("manual execute safety_guard", status, response)
    if result.get("status") != "succeeded":
        raise AgentBusinessToolsCheckError(f"manual safety_guard failed: {result}")
    record(state, "POST /api/agents/runs/{run_id}/execute-tool", "passed", result.get("summary", ""))

    status, response = request_json(
        "POST",
        f"/agents/runs/{state.run_id}/execute-tool",
        token=state.viewer_token,
        payload=payload,
    )
    expect_forbidden("viewer manual execute", status, response)
    record(state, "viewer execute-tool blocked", "passed", f"http={status}")


def check_approval_path(state: State) -> None:
    if not state.approval_id:
        raise AgentBusinessToolsCheckError("approval_id is missing")
    status, response = request_json(
        "POST",
        f"/agents/approvals/{state.approval_id}/approve",
        token=state.expert_token,
        payload={"review_comment": "Task22B draft approval verification."},
    )
    approval = api_data("expert approve", status, response)
    if approval.get("status") != "approved":
        raise AgentBusinessToolsCheckError(f"approval not approved: {approval}")
    record(state, "expert approval of tool drafts", "passed", approval["status"])


def main() -> int:
    state = State()
    try:
        ensure_seed()
        record(state, "seed_agent_runtime.py idempotency", "passed", "executed twice")
        ensure_users(state)
        record(state, "admin/engineer/expert/viewer login", "passed", "tokens acquired")
        check_tool_registry(state)
        ensure_device_fixture(state)
        check_full_tool_run(state)
        check_manual_execute_endpoint(state)
        check_approval_path(state)
    except Exception as exc:  # noqa: BLE001
        record(state, "agent business tools flow", "failed", str(exc))
        print(json.dumps({"status": "failed", "results": state.results}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"status": "passed", "results": state.results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
