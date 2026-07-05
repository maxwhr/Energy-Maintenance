from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402
from seed_agent_runtime import main as seed_agent_runtime  # noqa: E402
from seed_external_api_providers import main as seed_external_api_providers  # noqa: E402


API_BASE_URL = os.getenv("TASK22H_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("TASK22H_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22H_{RUN_ID}"
TEST_PASSWORD = os.getenv("TASK22H_TEST_PASSWORD", "Task22H_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("TASK22H_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("TASK22H_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class Task22HCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    engineer_token: str | None = None
    expert_token: str | None = None
    viewer_token: str | None = None
    device_id: str | None = None
    media_id: str | None = None
    diagnosis_run_id: str | None = None
    sop_run_id: str | None = None
    task_run_id: str | None = None
    sop_approval_id: str | None = None
    task_approval_id: str | None = None
    diagnosis_trace_id: str | None = None
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


def api_data(label: str, response: tuple[int, dict[str, Any]]) -> Any:
    status, body = response
    if status >= 400 or body.get("code") not in (0, 200):
        raise Task22HCheckError(
            f"{label} failed: http={status}, code={body.get('code')}, message={body.get('message')}"
        )
    return body.get("data")


def expect_forbidden(label: str, response: tuple[int, dict[str, Any]]) -> None:
    status, body = response
    if status in {401, 403} or (isinstance(body.get("code"), int) and body.get("code") not in {0, 200}):
        return
    raise Task22HCheckError(f"{label} should be forbidden, got http={status}, code={body.get('code')}")


def ensure_seed(state: State) -> None:
    if seed_agent_runtime() != 0:
        raise Task22HCheckError("seed_agent_runtime.py failed")
    if seed_external_api_providers() != 0:
        raise Task22HCheckError("seed_external_api_providers.py failed")
    record(state, "seed agent runtime and external providers", "passed", "idempotent=true")


def ensure_users(state: State) -> None:
    state.admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        cga.ensure_user(state.admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", token)
    record(state, "login admin/engineer/expert/viewer", "passed", "tokens acquired")


def create_device(state: State) -> None:
    payload = {
        "device_code": f"{MARKER}_DEV",
        "device_name": f"{MARKER} Huawei SUN2000 inverter",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-50KTL",
        "device_type": "pv_inverter",
        "station_name": f"{MARKER} demo station",
        "location": "Task22H acceptance bay",
        "status": "fault",
        "metadata_json": {"marker": MARKER},
        "description": f"{MARKER} device for diagnosis/SOP/task agent orchestration.",
    }
    device = api_data(
        "create Task22H device",
        cga.request_json("POST", "/devices", token=state.engineer_token, payload=payload, timeout=30),
    )
    state.device_id = str(device["id"])
    record(state, "create Task22H device", "passed", state.device_id)


def upload_media(state: State) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} Huawei SUN2000 low insulation alarm screen"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
        ("device_id", state.device_id or ""),
        ("fault_type", "low_insulation_resistance"),
        ("alarm_code", f"{MARKER}_LOW_INSULATION"),
    ]
    body, content_type = cga.multipart_body(
        fields,
        "file",
        f"{MARKER}_pv_inverter_alarm.png",
        cga.SAMPLE_PNG,
        "image/png",
    )
    media = api_data(
        "upload Task22H media",
        cga.request_json(
            "POST",
            "/media/upload",
            token=state.engineer_token,
            body=body,
            content_type=content_type,
            timeout=60,
        ),
    )
    state.media_id = str(media.get("media_id") or media.get("id"))
    if not state.media_id:
        raise Task22HCheckError("media upload did not return media_id")
    record(state, "upload Task22H media", "passed", state.media_id)


def create_run(state: State, *, agent_code: str, token: str, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
    tools = {
        "fault_diagnosis_agent": [
            "device_lookup",
            "device_history",
            "media_lookup",
            "knowledge_search",
            "kg_business_context",
            "diagnosis_rule_engine",
            "safety_guard",
        ],
        "sop_planner_agent": ["device_lookup", "knowledge_search", "kg_business_context", "sop_generator", "safety_guard"],
        "task_orchestration_agent": [
            "device_lookup",
            "device_history",
            "record_center_lookup",
            "task_draft_creator",
            "safety_guard",
            "human_approval",
        ],
    }[agent_code]
    payload = {
        "agent_code": agent_code,
        "input_text": (
            f"{MARKER} SUN2000 逆变器低绝缘阻抗告警，现场潮湿，设备近期多次重启，"
            "请生成可追溯的诊断/SOP/工单草稿。"
        ),
        "device_id": state.device_id,
        "media_ids": [state.media_id] if state.media_id else [],
        "tools": tools,
        "context": {
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "fault_type": "low_insulation_resistance",
            "alarm_code": f"{MARKER}_LOW_INSULATION",
            "fault_description": f"{MARKER} low insulation alarm after humid weather.",
            "source": "task22h_check",
            **(extra_context or {}),
        },
        "tool_inputs": {
            "media_ocr": {"mock_run": False, "capability": "ocr"},
            "media_mimo_analysis": {"mock_run": False, "capability": "fault_scene_analysis"},
            "task_draft_creator": {"priority": "high"},
            "safety_guard": {"source": agent_code},
        },
        "dry_run": True,
        "mock_run": False,
    }
    run = api_data(
        f"create {agent_code}",
        cga.request_json("POST", "/agents/runs", token=token, payload=payload, timeout=90),
    )
    return timeline(state, str(run["run_id"]), token=token)


def timeline(state: State, run_id: str, *, token: str) -> dict[str, Any]:
    data = api_data(
        f"timeline {run_id}",
        cga.request_json("GET", f"/agents/runs/{run_id}/timeline", token=token, timeout=30),
    )
    for key in ("run", "steps", "tool_calls", "artifacts", "approvals", "events"):
        if key not in data:
            raise Task22HCheckError(f"timeline missing {key}")
    return data


def assert_steps(data: dict[str, Any], expected: list[str]) -> None:
    names = [item.get("step_name") for item in data.get("steps") or []]
    missing = [item for item in expected if item not in names]
    if missing:
        raise Task22HCheckError(f"missing steps: {missing}; got={names}")
    if any(not item.get("reasoning_summary") for item in data.get("steps") or []):
        raise Task22HCheckError("all agent steps must include reasoning_summary")


def artifact_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("artifact_type"): item for item in data.get("artifacts") or []}


def assert_artifacts(data: dict[str, Any], required: list[str]) -> dict[str, dict[str, Any]]:
    artifacts = artifact_map(data)
    missing = [item for item in required if item not in artifacts]
    if missing:
        raise Task22HCheckError(f"missing artifacts: {missing}")
    return artifacts


def check_diagnosis_agent(state: State) -> None:
    data = create_run(state, agent_code="fault_diagnosis_agent", token=state.engineer_token or "")
    state.diagnosis_run_id = data["run"]["run_id"]
    assert_steps(
        data,
        [
            "validate_diagnosis_input",
            "load_device_context",
            "load_device_history",
            "load_multimodal_evidence",
            "retrieve_approved_knowledge",
            "query_knowledge_graph",
            "run_diagnosis_rules",
            "run_safety_guard",
            "build_diagnosis_summary",
            "create_trace_links",
            "finalize_diagnosis_agent_run",
        ],
    )
    artifacts = assert_artifacts(data, ["diagnosis_summary", "safety_checklist", "evidence_trace_summary"])
    diagnosis = artifacts["diagnosis_summary"].get("content_json") or {}
    if not diagnosis.get("requires_human_review") or not diagnosis.get("possible_causes"):
        raise Task22HCheckError("diagnosis_summary artifact is incomplete")
    state.diagnosis_trace_id = diagnosis.get("diagnosis_trace_id")
    final_answer = str((data.get("run") or {}).get("final_answer") or "")
    if "不是最终维修结论" not in final_answer:
        raise Task22HCheckError("diagnosis final_answer must state result is not final repair conclusion")
    record(state, "fault_diagnosis_agent dry-run", "passed", state.diagnosis_run_id)


def check_sop_agent(state: State) -> None:
    data = create_run(
        state,
        agent_code="sop_planner_agent",
        token=state.engineer_token or "",
        extra_context={"diagnosis_trace_id": state.diagnosis_trace_id},
    )
    state.sop_run_id = data["run"]["run_id"]
    assert_steps(
        data,
        [
            "validate_sop_input",
            "load_device_context",
            "load_diagnosis_context",
            "retrieve_sop_related_knowledge",
            "query_sop_kg_context",
            "generate_sop_draft",
            "build_safety_checklist",
            "create_sop_artifact",
            "create_approval_request",
            "finalize_sop_agent_run",
        ],
    )
    artifacts = assert_artifacts(data, ["sop_draft", "safety_checklist", "evidence_trace_summary"])
    sop = artifacts["sop_draft"].get("content_json") or {}
    if not sop.get("requires_approval") or not sop.get("steps"):
        raise Task22HCheckError("sop_draft artifact is incomplete")
    approvals = data.get("approvals") or []
    approval = next((item for item in approvals if item.get("approval_type") == "sop_draft_review"), None)
    if not approval or approval.get("status") != "pending":
        raise Task22HCheckError("SOP approval pending record missing")
    state.sop_approval_id = approval["id"]
    approved = api_data(
        "expert approve SOP draft",
        cga.request_json(
            "POST",
            f"/agents/approvals/{state.sop_approval_id}/approve",
            token=state.expert_token,
            payload={"review_comment": "Task22H SOP draft approved."},
            timeout=30,
        ),
    )
    if approved.get("status") != "approved":
        raise Task22HCheckError("SOP approval was not approved")
    record(state, "sop_planner_agent dry-run and approval", "passed", state.sop_run_id)


def count_marker_tasks(state: State) -> int:
    page = api_data(
        "list maintenance tasks by Task22H marker",
        cga.request_json(
            "GET",
            f"/maintenance/tasks?{cga.encode_query({'keyword': MARKER, 'page': 1, 'page_size': 50})}",
            token=state.expert_token,
            timeout=30,
        ),
    )
    return int((page or {}).get("total") or 0)


def check_task_agent(state: State) -> None:
    before = count_marker_tasks(state)
    data = create_run(state, agent_code="task_orchestration_agent", token=state.engineer_token or "")
    state.task_run_id = data["run"]["run_id"]
    assert_steps(
        data,
        [
            "validate_task_input",
            "load_device_context",
            "load_recent_history",
            "build_task_draft",
            "build_safety_requirement",
            "create_task_artifact",
            "create_approval_request",
            "finalize_task_agent_run",
        ],
    )
    artifacts = assert_artifacts(data, ["task_draft", "safety_checklist", "evidence_trace_summary"])
    task = artifacts["task_draft"].get("content_json") or {}
    if not task.get("requires_approval") or task.get("formal_task_created") is not False:
        raise Task22HCheckError("task_draft artifact should require approval and not create formal task")
    approvals = data.get("approvals") or []
    approval = next((item for item in approvals if item.get("approval_type") == "task_draft_review"), None)
    if not approval or approval.get("status") != "pending":
        raise Task22HCheckError("Task approval pending record missing")
    state.task_approval_id = approval["id"]
    rejected = api_data(
        "expert reject task draft",
        cga.request_json(
            "POST",
            f"/agents/approvals/{state.task_approval_id}/reject",
            token=state.expert_token,
            payload={"review_comment": "Task22H task draft rejection path verified."},
            timeout=30,
        ),
    )
    if rejected.get("status") != "rejected":
        raise Task22HCheckError("Task approval was not rejected")
    after = count_marker_tasks(state)
    if after != before:
        raise Task22HCheckError(f"formal maintenance_task count changed: before={before}, after={after}")
    record(state, "task_orchestration_agent dry-run and no formal task", "passed", state.task_run_id)


def check_viewer_blocked(state: State) -> None:
    payload = {
        "agent_code": "fault_diagnosis_agent",
        "input_text": "viewer should be blocked",
        "tools": ["diagnosis_rule_engine"],
        "dry_run": True,
    }
    expect_forbidden(
        "viewer create diagnosis agent run",
        cga.request_json("POST", "/agents/runs", token=state.viewer_token, payload=payload, timeout=20),
    )
    if state.sop_approval_id:
        expect_forbidden(
            "viewer approve SOP approval",
            cga.request_json(
                "POST",
                f"/agents/approvals/{state.sop_approval_id}/approve",
                token=state.viewer_token,
                payload={"review_comment": "viewer should be rejected"},
                timeout=20,
            ),
        )
    record(state, "viewer create/approve blocked", "passed", "403 or business error")


def check_records_and_no_package(state: State) -> None:
    for run_id in (state.diagnosis_run_id, state.sop_run_id, state.task_run_id):
        data = timeline(state, run_id or "", token=state.engineer_token or "")
        if not data.get("tool_calls") or not data.get("steps") or not data.get("artifacts") or not data.get("events"):
            raise Task22HCheckError(f"run {run_id} is missing records in timeline")
    if delivery_zip_snapshot() != state.zip_snapshot:
        raise Task22HCheckError("delivery zip snapshot changed during Task22H")
    record(state, "agent runtime records and no package", "passed", "steps/tool_calls/artifacts/events verified")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed(state)
        ensure_users(state)
        create_device(state)
        upload_media(state)
        check_diagnosis_agent(state)
        check_sop_agent(state)
        check_task_agent(state)
        check_viewer_blocked(state)
        check_records_and_no_package(state)
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] Task22H diagnosis/SOP/task agent flow: {exc}")
        return 1
    print(
        "task22h_diagnosis_sop_task_agent_flow_result "
        f"checks={len(state.results)} device_id={state.device_id} media_id={state.media_id} "
        f"diagnosis_run_id={state.diagnosis_run_id} sop_run_id={state.sop_run_id} task_run_id={state.task_run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
