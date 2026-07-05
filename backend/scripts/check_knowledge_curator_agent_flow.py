from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models import KGEdge, KGNode, KnowledgeChunk, KnowledgeContribution, KnowledgeDocument  # noqa: E402
from seed_agent_runtime import main as seed_agent_runtime  # noqa: E402
from seed_external_api_providers import main as seed_external_api_providers  # noqa: E402


API_BASE_URL = os.getenv("TASK22I_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("TASK22I_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22I_{RUN_ID}"
TEST_PASSWORD = os.getenv("TASK22I_TEST_PASSWORD", "Task22I_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("TASK22I_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("TASK22I_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class Task22ICheckError(AssertionError):
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
    curator_run_id: str | None = None
    curator_approval_id: str | None = None
    formal_counts_before: dict[str, int] = field(default_factory=dict)
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


def formal_counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        return {
            "knowledge_contributions": int(db.scalar(select(func.count()).select_from(KnowledgeContribution)) or 0),
            "knowledge_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "knowledge_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
            "kg_nodes": int(db.scalar(select(func.count()).select_from(KGNode)) or 0),
            "kg_edges": int(db.scalar(select(func.count()).select_from(KGEdge)) or 0),
        }
    finally:
        db.close()


def api_data(label: str, response: tuple[int, dict[str, Any]]) -> Any:
    status, body = response
    if status >= 400 or body.get("code") not in (0, 200):
        raise Task22ICheckError(
            f"{label} failed: http={status}, code={body.get('code')}, message={body.get('message')}"
        )
    return body.get("data")


def expect_forbidden(label: str, response: tuple[int, dict[str, Any]]) -> None:
    status, body = response
    if status in {401, 403} or (isinstance(body.get("code"), int) and body.get("code") not in {0, 200}):
        return
    raise Task22ICheckError(f"{label} should be forbidden, got http={status}, code={body.get('code')}")


def ensure_seed(state: State) -> None:
    if seed_agent_runtime() != 0:
        raise Task22ICheckError("seed_agent_runtime.py failed")
    if seed_external_api_providers() != 0:
        raise Task22ICheckError("seed_external_api_providers.py failed")
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
        "location": "Task22I acceptance bay",
        "status": "fault",
        "metadata_json": {"marker": MARKER},
        "description": f"{MARKER} device for knowledge curator agent.",
    }
    device = api_data(
        "create Task22I device",
        cga.request_json("POST", "/devices", token=state.engineer_token, payload=payload, timeout=30),
    )
    state.device_id = str(device["id"])
    record(state, "create Task22I device", "passed", state.device_id)


def upload_media(state: State) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} Huawei SUN2000 low insulation site evidence"),
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
        f"{MARKER}_pv_inverter_site.png",
        cga.SAMPLE_PNG,
        "image/png",
    )
    media = api_data(
        "upload Task22I media",
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
        raise Task22ICheckError("media upload did not return media_id")
    record(state, "upload Task22I media", "passed", state.media_id)


def create_agent_run(
    state: State,
    *,
    agent_code: str,
    token: str,
    tools: list[str],
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "agent_code": agent_code,
        "input_text": (
            f"{MARKER} SUN2000 inverter low insulation alarm after humid weather. "
            "Build traceable diagnosis/SOP/task/knowledge draft evidence."
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
            "engineer_notes": "Field retest recovered after insulation check; humidity around combiner box was high.",
            "source": "task22i_check",
            **(extra_context or {}),
        },
        "tool_inputs": {
            "media_ocr": {"mock_run": False, "capability": "ocr"},
            "media_mimo_analysis": {"mock_run": False, "capability": "fault_scene_analysis"},
            "task_draft_creator": {"priority": "high"},
            "knowledge_contribution_draft_creator": {"category": "maintenance_experience"},
            "safety_guard": {"source": agent_code},
        },
        "dry_run": True,
        "mock_run": False,
    }
    run = api_data(
        f"create {agent_code}",
        cga.request_json("POST", "/agents/runs", token=token, payload=payload, timeout=90),
    )
    return timeline(str(run["run_id"]), token=token)


def timeline(run_id: str, *, token: str) -> dict[str, Any]:
    data = api_data(
        f"timeline {run_id}",
        cga.request_json("GET", f"/agents/runs/{run_id}/timeline", token=token, timeout=30),
    )
    for key in ("run", "steps", "tool_calls", "artifacts", "approvals", "events"):
        if key not in data:
            raise Task22ICheckError(f"timeline missing {key}")
    return data


def assert_steps(data: dict[str, Any], expected: list[str]) -> None:
    names = [item.get("step_name") for item in data.get("steps") or []]
    missing = [item for item in expected if item not in names]
    if missing:
        raise Task22ICheckError(f"missing steps: {missing}; got={names}")
    if any(not item.get("reasoning_summary") for item in data.get("steps") or []):
        raise Task22ICheckError("all agent steps must include reasoning_summary")


def artifact_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("artifact_type"): item for item in data.get("artifacts") or []}


def assert_artifacts(data: dict[str, Any], required: list[str]) -> dict[str, dict[str, Any]]:
    artifacts = artifact_map(data)
    missing = [item for item in required if item not in artifacts]
    if missing:
        raise Task22ICheckError(f"missing artifacts: {missing}")
    return artifacts


def create_source_runs(state: State) -> None:
    diagnosis = create_agent_run(
        state,
        agent_code="fault_diagnosis_agent",
        token=state.engineer_token or "",
        tools=[
            "device_lookup",
            "device_history",
            "media_lookup",
            "knowledge_search",
            "kg_business_context",
            "diagnosis_rule_engine",
            "safety_guard",
        ],
    )
    state.diagnosis_run_id = diagnosis["run"]["run_id"]
    sop = create_agent_run(
        state,
        agent_code="sop_planner_agent",
        token=state.engineer_token or "",
        tools=["device_lookup", "knowledge_search", "kg_business_context", "sop_generator", "safety_guard"],
        extra_context={"diagnosis_trace_id": (artifact_map(diagnosis).get("diagnosis_summary") or {}).get("content_json", {}).get("diagnosis_trace_id")},
    )
    state.sop_run_id = sop["run"]["run_id"]
    task = create_agent_run(
        state,
        agent_code="task_orchestration_agent",
        token=state.engineer_token or "",
        tools=["device_lookup", "device_history", "record_center_lookup", "task_draft_creator", "safety_guard", "human_approval"],
    )
    state.task_run_id = task["run"]["run_id"]
    record(
        state,
        "create source diagnosis/SOP/task agent runs",
        "passed",
        f"{state.diagnosis_run_id},{state.sop_run_id},{state.task_run_id}",
    )


def check_knowledge_curator_agent(state: State) -> None:
    before = formal_counts()
    data = create_agent_run(
        state,
        agent_code="knowledge_curator_agent",
        token=state.engineer_token or "",
        tools=[
            "device_lookup",
            "device_history",
            "record_center_lookup",
            "knowledge_search",
            "kg_business_context",
            "media_lookup",
            "safety_guard",
            "knowledge_contribution_draft_creator",
            "human_approval",
        ],
        extra_context={
            "source_agent_run_ids": [state.diagnosis_run_id, state.sop_run_id, state.task_run_id],
            "engineer_notes": "Humidity was high near the combiner box; insulation retest passed after drying.",
        },
    )
    state.curator_run_id = data["run"]["run_id"]
    assert_steps(
        data,
        [
            "validate_curator_input",
            "load_device_context",
            "load_device_history",
            "load_source_agent_artifacts",
            "load_media_evidence",
            "search_existing_knowledge",
            "query_kg_context",
            "run_safety_guard",
            "build_maintenance_case_summary",
            "build_knowledge_contribution_draft",
            "build_kg_candidate_suggestion",
            "create_approval_request",
            "create_evidence_trace",
            "finalize_curator_run",
        ],
    )
    tool_names = {item.get("tool_name") for item in data.get("tool_calls") or []}
    for tool in [
        "device_lookup",
        "device_history",
        "record_center_lookup",
        "knowledge_search",
        "kg_business_context",
        "media_lookup",
        "safety_guard",
        "knowledge_contribution_draft_creator",
        "human_approval",
    ]:
        if tool not in tool_names:
            raise Task22ICheckError(f"missing tool_call for {tool}")
    artifacts = assert_artifacts(
        data,
        [
            "maintenance_case_summary",
            "knowledge_contribution_draft",
            "kg_candidate_suggestion",
            "evidence_trace_summary",
            "safety_checklist",
        ],
    )
    draft = artifacts["knowledge_contribution_draft"].get("content_json") or {}
    if not draft.get("requires_expert_review") or draft.get("formal_contribution_created") is not False:
        raise Task22ICheckError("knowledge_contribution_draft artifact boundary is incomplete")
    if "duplicate_risk" not in draft or "limitations" not in draft:
        raise Task22ICheckError("knowledge_contribution_draft must include duplicate_risk and limitations")
    kg = artifacts["kg_candidate_suggestion"].get("content_json") or {}
    if kg.get("formal_kg_write_created") is not False or not kg.get("requires_kg_review"):
        raise Task22ICheckError("kg_candidate_suggestion must be artifact-only and review-gated")
    approvals = data.get("approvals") or []
    approval = next((item for item in approvals if item.get("approval_type") == "knowledge_contribution_draft_review"), None)
    if not approval or approval.get("status") != "pending":
        raise Task22ICheckError("knowledge contribution draft approval pending record missing")
    state.curator_approval_id = approval["id"]
    final_answer = str((data.get("run") or {}).get("final_answer") or "")
    for text in ("草稿", "专家审核", "尚未入库", "未创建正式"):
        if text not in final_answer:
            raise Task22ICheckError(f"final_answer missing boundary text: {text}")
    after = formal_counts()
    if after != before:
        raise Task22ICheckError(f"formal knowledge/KG counts changed before approval: before={before}, after={after}")
    state.formal_counts_before = before
    record(state, "knowledge_curator_agent dry-run", "passed", state.curator_run_id)


def check_approval_and_formal_write_boundary(state: State) -> None:
    if not state.curator_approval_id:
        raise Task22ICheckError("curator approval id missing")
    approved = api_data(
        "expert approve knowledge contribution draft",
        cga.request_json(
            "POST",
            f"/agents/approvals/{state.curator_approval_id}/approve",
            token=state.expert_token,
            payload={"review_comment": "Task22I knowledge curation draft approval verified."},
            timeout=30,
        ),
    )
    if approved.get("status") != "approved":
        raise Task22ICheckError("knowledge curator approval was not approved")
    after = formal_counts()
    if after != state.formal_counts_before:
        raise Task22ICheckError(
            f"approval changed formal knowledge/KG counts: before={state.formal_counts_before}, after={after}"
        )
    record(state, "approval only updates agent approval", "passed", "formal knowledge/KG counts unchanged")


def check_viewer_blocked(state: State) -> None:
    payload = {
        "agent_code": "knowledge_curator_agent",
        "input_text": "viewer should be blocked",
        "tools": ["knowledge_contribution_draft_creator"],
        "dry_run": True,
    }
    expect_forbidden(
        "viewer create knowledge curator run",
        cga.request_json("POST", "/agents/runs", token=state.viewer_token, payload=payload, timeout=20),
    )
    if state.curator_approval_id:
        expect_forbidden(
            "viewer approve knowledge curator approval",
            cga.request_json(
                "POST",
                f"/agents/approvals/{state.curator_approval_id}/approve",
                token=state.viewer_token,
                payload={"review_comment": "viewer should be rejected"},
                timeout=20,
            ),
        )
    record(state, "viewer create/approve blocked", "passed", "403 or business error")


def check_records_and_no_package(state: State) -> None:
    data = timeline(state.curator_run_id or "", token=state.engineer_token or "")
    if not data.get("tool_calls") or not data.get("steps") or not data.get("artifacts") or not data.get("events"):
        raise Task22ICheckError("knowledge curator run is missing timeline records")
    if delivery_zip_snapshot() != state.zip_snapshot:
        raise Task22ICheckError("delivery zip snapshot changed during Task22I")
    record(state, "agent runtime records and no package", "passed", "steps/tool_calls/artifacts/events verified")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed(state)
        ensure_users(state)
        create_device(state)
        upload_media(state)
        create_source_runs(state)
        check_knowledge_curator_agent(state)
        check_approval_and_formal_write_boundary(state)
        check_viewer_blocked(state)
        check_records_and_no_package(state)
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] Task22I knowledge curator agent flow: {exc}")
        return 1
    print(
        "task22i_knowledge_curator_agent_flow_result "
        f"checks={len(state.results)} device_id={state.device_id} media_id={state.media_id} "
        f"curator_run_id={state.curator_run_id} approval_id={state.curator_approval_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
