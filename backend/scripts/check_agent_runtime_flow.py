from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, parse, request

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402

API_BASE_URL = os.getenv("AGENT_RUNTIME_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("AGENT_RUNTIME_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22A_{RUN_ID}"
TEST_PASSWORD = os.getenv("AGENT_RUNTIME_TEST_PASSWORD", "Task22A_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("AGENT_RUNTIME_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("AGENT_RUNTIME_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class AgentRuntimeCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    expert_token: str | None = None
    engineer_token: str | None = None
    viewer_token: str | None = None
    run_id: str | None = None
    approval_run_id: str | None = None
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
        raise AgentRuntimeCheckError(
            f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}"
        )
    return response.get("data")


def expect_forbidden(label: str, status: int, response: dict[str, Any]) -> None:
    code = response.get("code")
    if status in (401, 403) or (isinstance(code, int) and code not in (0, 200)):
        return
    raise AgentRuntimeCheckError(f"{label} should be forbidden, got http={status}, code={code}")


def ensure_seed() -> None:
    from seed_agent_runtime import main as seed_main

    first = seed_main()
    second = seed_main()
    if first != 0 or second != 0:
        raise AgentRuntimeCheckError("seed_agent_runtime.py did not return success twice")


def ensure_users(state: State) -> None:
    admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    state.admin_token = admin_token
    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        cga.ensure_user(admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", token)


def check_definitions_and_tools(state: State) -> None:
    status, response = request_json("GET", "/agents/definitions", token=state.viewer_token)
    definitions = api_data("definitions", status, response)
    codes = {item.get("agent_code") for item in definitions}
    expected = {
        "multimodal_evidence_agent",
        "retrieval_qa_agent",
        "fault_diagnosis_agent",
        "sop_planner_agent",
        "task_orchestration_agent",
        "knowledge_curator_agent",
        "safety_guard_agent",
    }
    if not expected.issubset(codes):
        raise AgentRuntimeCheckError(f"missing agent definitions: {sorted(expected - codes)}")
    record(state, "GET /api/agents/definitions", "passed", f"count={len(definitions)}")

    status, response = request_json("GET", "/agents/definitions/retrieval_qa_agent", token=state.viewer_token)
    api_data("definition detail", status, response)
    record(state, "GET /api/agents/definitions/{agent_code}", "passed", "retrieval_qa_agent")

    status, response = request_json("GET", "/agents/tools", token=state.viewer_token)
    tools = api_data("tools", status, response)
    by_name = {item.get("tool_name"): item for item in tools}
    mimo = by_name.get("media_mimo_analysis")
    if not mimo:
        raise AgentRuntimeCheckError("media_mimo_analysis tool missing")
    metadata = mimo.get("metadata_json") or {}
    if mimo.get("enabled") is not False or metadata.get("status") != "blocked":
        raise AgentRuntimeCheckError(f"media_mimo_analysis is not blocked/disabled: {mimo}")
    record(state, "GET /api/agents/tools", "passed", "media_mimo_analysis disabled/blocked")


def check_run_flow(state: State) -> None:
    payload = {
        "agent_code": "retrieval_qa_agent",
        "input_text": "华为 SUN2000 逆变器绝缘告警如何排查？",
        "tool_names": ["knowledge_search", "safety_guard"],
        "dry_run": True,
    }
    status, response = request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload)
    run = api_data("engineer create run", status, response)
    if run.get("status") != "succeeded":
        raise AgentRuntimeCheckError(f"expected succeeded run, got {run}")
    state.run_id = run["run_id"]
    record(state, "engineer POST /api/agents/runs", "passed", state.run_id)

    for suffix, label in [
        ("", "run detail"),
        ("/steps", "run steps"),
        ("/tool-calls", "tool calls"),
        ("/artifacts", "artifacts"),
    ]:
        status, response = request_json("GET", f"/agents/runs/{state.run_id}{suffix}", token=state.engineer_token)
        data = api_data(label, status, response)
        if suffix and not data:
            raise AgentRuntimeCheckError(f"{label} returned empty data")
        record(state, f"GET /api/agents/runs/{{run_id}}{suffix}", "passed", label)

    status, response = request_json("GET", "/agents/events", token=state.engineer_token)
    events_page = api_data("events", status, response)
    if not events_page.get("items"):
        raise AgentRuntimeCheckError("events page is empty")
    record(state, "GET /api/agents/events", "passed", f"items={len(events_page['items'])}")

    status, response = request_json("POST", "/agents/runs", token=state.viewer_token, payload=payload)
    expect_forbidden("viewer create run", status, response)
    record(state, "viewer POST /api/agents/runs blocked", "passed", f"http={status}")


def check_approval_flow(state: State) -> None:
    payload = {
        "agent_code": "task_orchestration_agent",
        "input_text": "生成一条逆变器过温告警任务草案。",
        "tool_names": ["task_draft_creator", "human_approval"],
        "requires_approval": True,
        "dry_run": True,
    }
    status, response = request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload)
    run = api_data("approval run", status, response)
    if run.get("status") != "waiting_approval":
        raise AgentRuntimeCheckError(f"approval run should be waiting_approval, got {run}")
    state.approval_run_id = run["run_id"]

    status, response = request_json("GET", f"/agents/runs/{state.approval_run_id}/approvals", token=state.engineer_token)
    approvals = api_data("run approvals", status, response)
    if not approvals:
        raise AgentRuntimeCheckError("approval run did not create approval")
    state.approval_id = approvals[0]["id"]
    record(state, "approval record created", "passed", state.approval_id)

    status, response = request_json(
        "POST",
        f"/agents/approvals/{state.approval_id}/approve",
        token=state.viewer_token,
        payload={"review_comment": "viewer should be blocked"},
    )
    expect_forbidden("viewer approve", status, response)
    record(state, "viewer approve blocked", "passed", f"http={status}")

    status, response = request_json(
        "POST",
        f"/agents/approvals/{state.approval_id}/approve",
        token=state.expert_token,
        payload={"review_comment": "Task22A approval flow verified."},
    )
    approval = api_data("expert approve", status, response)
    if approval.get("status") != "approved":
        raise AgentRuntimeCheckError(f"approval not approved: {approval}")
    record(state, "expert/admin approval path", "passed", approval["status"])


def main() -> int:
    state = State()
    try:
        ensure_seed()
        record(state, "seed_agent_runtime.py idempotency", "passed", "executed twice")
        ensure_users(state)
        record(state, "admin/engineer/expert/viewer login", "passed", "tokens acquired")
        check_definitions_and_tools(state)
        check_run_flow(state)
        check_approval_flow(state)
    except Exception as exc:  # noqa: BLE001
        record(state, "agent runtime flow", "failed", str(exc))
        print(json.dumps({"status": "failed", "results": state.results}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"status": "passed", "results": state.results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
