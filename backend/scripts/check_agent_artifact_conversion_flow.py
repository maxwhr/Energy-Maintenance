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
from app.models import (  # noqa: E402
    AgentArtifactConversion,
    AgentEventLog,
    DeviceMaintenanceRecord,
    KGCandidate,
    KGEdge,
    KGExtractionRun,
    KGNode,
    KnowledgeChunk,
    KnowledgeContribution,
    KnowledgeDocument,
    MaintenanceTask,
    SOPExecutionRecord,
    SOPTemplate,
)
from seed_agent_runtime import main as seed_agent_runtime  # noqa: E402
from seed_external_api_providers import main as seed_external_api_providers  # noqa: E402


API_BASE_URL = os.getenv("TASK22J_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("TASK22J_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22J_{RUN_ID}"
TEST_PASSWORD = os.getenv("TASK22J_TEST_PASSWORD", "Task22J_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("TASK22J_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("TASK22J_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class Task22JCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    engineer_token: str | None = None
    expert_token: str | None = None
    viewer_token: str | None = None
    device_id: str | None = None
    media_id: str | None = None
    sop_artifact_id: str | None = None
    sop_approval_id: str | None = None
    task_artifact_id: str | None = None
    task_approval_id: str | None = None
    contribution_artifact_id: str | None = None
    kg_artifact_id: str | None = None
    curator_approval_id: str | None = None
    conversion_trace_ids: list[str] = field(default_factory=list)
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


def counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        models = {
            "knowledge_contributions": KnowledgeContribution,
            "knowledge_documents": KnowledgeDocument,
            "knowledge_chunks": KnowledgeChunk,
            "sop_templates": SOPTemplate,
            "sop_execution_records": SOPExecutionRecord,
            "maintenance_tasks": MaintenanceTask,
            "device_maintenance_records": DeviceMaintenanceRecord,
            "kg_extraction_runs": KGExtractionRun,
            "kg_candidates": KGCandidate,
            "kg_nodes": KGNode,
            "kg_edges": KGEdge,
            "agent_artifact_conversions": AgentArtifactConversion,
        }
        return {
            name: int(db.scalar(select(func.count()).select_from(model)) or 0)
            for name, model in models.items()
        }
    finally:
        db.close()


def api_data(label: str, response: tuple[int, dict[str, Any]]) -> Any:
    status, body = response
    if status >= 400 or body.get("code") not in (0, 200):
        raise Task22JCheckError(
            f"{label} failed: http={status}, code={body.get('code')}, message={body.get('message')}"
        )
    return body.get("data")


def expect_blocked(label: str, response: tuple[int, dict[str, Any]]) -> None:
    status, body = response
    code = body.get("code")
    if status in {401, 403} or (isinstance(code, int) and code not in {0, 200}):
        return
    raise Task22JCheckError(f"{label} should be blocked, got http={status}, code={code}, body={body}")


def expect_already_converted(label: str, response: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    data = api_data(label, response)
    if data.get("status") not in {"already_converted", "conversion_in_progress"} and not data.get("already_converted"):
        raise Task22JCheckError(f"{label} should return already_converted/conflict, got {data}")
    return data


def ensure_seed(state: State) -> None:
    if seed_agent_runtime() != 0:
        raise Task22JCheckError("seed_agent_runtime.py failed")
    if seed_external_api_providers() != 0:
        raise Task22JCheckError("seed_external_api_providers.py failed")
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
        "location": "Task22J acceptance bay",
        "status": "fault",
        "metadata_json": {"marker": MARKER},
        "description": f"{MARKER} device for artifact conversion.",
    }
    device = api_data(
        "create Task22J device",
        cga.request_json("POST", "/devices", token=state.engineer_token, payload=payload, timeout=30),
    )
    state.device_id = str(device["id"])
    record(state, "create Task22J device", "passed", state.device_id)


def upload_media(state: State) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} Huawei SUN2000 low insulation evidence"),
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
        "upload Task22J media",
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
        raise Task22JCheckError("media upload did not return media_id")
    record(state, "upload Task22J media", "passed", state.media_id)


def timeline(run_id: str, *, token: str) -> dict[str, Any]:
    data = api_data(
        f"timeline {run_id}",
        cga.request_json("GET", f"/agents/runs/{run_id}/timeline", token=token, timeout=30),
    )
    for key in ("run", "steps", "tool_calls", "artifacts", "approvals", "events"):
        if key not in data:
            raise Task22JCheckError(f"timeline missing {key}")
    return data


def artifact(data: dict[str, Any], artifact_type: str) -> dict[str, Any]:
    match = next((item for item in data.get("artifacts") or [] if item.get("artifact_type") == artifact_type), None)
    if not match:
        raise Task22JCheckError(f"artifact missing: {artifact_type}")
    return match


def approval(data: dict[str, Any], approval_type: str) -> dict[str, Any]:
    match = next((item for item in data.get("approvals") or [] if item.get("approval_type") == approval_type), None)
    if not match:
        raise Task22JCheckError(f"approval missing: {approval_type}")
    return match


def create_run(state: State, *, agent_code: str, tools: list[str], extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "agent_code": agent_code,
        "input_text": (
            f"{MARKER} SUN2000 inverter low insulation alarm after humid weather. "
            "Build approved draft artifacts for conversion validation."
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
            "engineer_notes": "Humidity was high near the combiner box; insulation retest passed after drying.",
            "source": "task22j_conversion_check",
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
        cga.request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload, timeout=90),
    )
    return timeline(str(run["run_id"]), token=state.engineer_token or "")


def approve(state: State, approval_id: str, label: str) -> None:
    result = api_data(
        f"approve {label}",
        cga.request_json(
            "POST",
            f"/agents/approvals/{approval_id}/approve",
            token=state.expert_token,
            payload={"review_comment": f"{MARKER} {label} approved for conversion."},
            timeout=30,
        ),
    )
    if result.get("status") != "approved":
        raise Task22JCheckError(f"{label} approval not approved")


def convert(
    state: State,
    artifact_id: str,
    target_type: str,
    approval_id: str,
    *,
    token: str | None = None,
    override_warnings: bool = False,
) -> dict[str, Any]:
    data = api_data(
        f"convert {target_type}",
        cga.request_json(
            "POST",
            f"/agents/artifacts/{artifact_id}/convert",
            token=token or state.expert_token,
            payload={
                "target_type": target_type,
                "approval_id": approval_id,
                "override_warnings": override_warnings,
                "comment": f"{MARKER} conversion acceptance.",
            },
            timeout=30,
        ),
    )
    trace_id = data.get("conversion_trace_id")
    target_id = data.get("target_id")
    if not trace_id or not target_id:
        raise Task22JCheckError(f"{target_type} conversion did not return trace_id and target_id")
    state.conversion_trace_ids.append(str(trace_id))
    return data


def check_status_and_detail(state: State, artifact_id: str, target_type: str, trace_id: str) -> None:
    status = api_data(
        "conversion status",
        cga.request_json("GET", f"/agents/artifacts/{artifact_id}/conversion-status", token=state.viewer_token, timeout=30),
    )
    if target_type not in (status.get("converted_targets") or {}):
        raise Task22JCheckError(f"conversion status does not include target {target_type}")
    listing = api_data(
        "conversion list",
        cga.request_json("GET", "/agents/conversions?page=1&page_size=20", token=state.expert_token, timeout=30),
    )
    if not any(item.get("conversion_trace_id") == trace_id for item in (listing.get("items") or [])):
        raise Task22JCheckError("conversion list did not include trace")
    detail = api_data(
        "conversion detail",
        cga.request_json("GET", f"/agents/conversions/{trace_id}", token=state.expert_token, timeout=30),
    )
    if detail.get("conversion_trace_id") != trace_id:
        raise Task22JCheckError("conversion detail trace mismatch")
    if not detail.get("id") or detail.get("conversion_status") != "succeeded":
        raise Task22JCheckError("conversion detail missing id or succeeded status")
    by_artifact = api_data(
        "artifact conversion history",
        cga.request_json("GET", f"/agents/artifacts/{artifact_id}/conversions", token=state.expert_token, timeout=30),
    )
    if not any(item.get("conversion_trace_id") == trace_id for item in by_artifact):
        raise Task22JCheckError("artifact conversion history did not include trace")
    by_run = api_data(
        "run conversion history",
        cga.request_json("GET", f"/agents/runs/{detail['source_agent_run_id']}/conversions", token=state.expert_token, timeout=30),
    )
    if not any(item.get("conversion_trace_id") == trace_id for item in by_run):
        raise Task22JCheckError("run conversion history did not include trace")


def create_sop_and_task_sources(state: State) -> None:
    sop_data = create_run(
        state,
        agent_code="sop_planner_agent",
        tools=["device_lookup", "knowledge_search", "kg_business_context", "sop_generator", "safety_guard"],
    )
    state.sop_artifact_id = artifact(sop_data, "sop_draft")["id"]
    state.sop_approval_id = approval(sop_data, "sop_draft_review")["id"]

    task_data = create_run(
        state,
        agent_code="task_orchestration_agent",
        tools=["device_lookup", "device_history", "record_center_lookup", "task_draft_creator", "safety_guard", "human_approval"],
    )
    state.task_artifact_id = artifact(task_data, "task_draft")["id"]
    state.task_approval_id = approval(task_data, "task_draft_review")["id"]
    record(state, "create SOP/task draft artifacts", "passed", f"sop={state.sop_artifact_id} task={state.task_artifact_id}")


def create_curator_source(state: State) -> None:
    data = create_run(
        state,
        agent_code="knowledge_curator_agent",
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
        extra_context={"source_agent_run_ids": []},
    )
    state.contribution_artifact_id = artifact(data, "knowledge_contribution_draft")["id"]
    state.kg_artifact_id = artifact(data, "kg_candidate_suggestion")["id"]
    state.curator_approval_id = approval(data, "knowledge_contribution_draft_review")["id"]
    record(
        state,
        "create knowledge contribution and KG candidate artifacts",
        "passed",
        f"contribution={state.contribution_artifact_id} kg={state.kg_artifact_id}",
    )


def check_approval_boundaries(state: State) -> None:
    expect_blocked(
        "convert SOP before approval",
        cga.request_json(
            "POST",
            f"/agents/artifacts/{state.sop_artifact_id}/convert",
            token=state.expert_token,
            payload={"target_type": "sop_template", "approval_id": state.sop_approval_id},
            timeout=30,
        ),
    )
    before = counts()
    approve(state, state.sop_approval_id or "", "sop draft")
    after = counts()
    if after != before:
        raise Task22JCheckError(f"approval changed formal counts before conversion: before={before}, after={after}")
    record(state, "approval does not auto-convert", "passed", "formal counts unchanged after approval")


def check_conversions(state: State) -> None:
    base = counts()
    sop = convert(state, state.sop_artifact_id or "", "sop_template", state.sop_approval_id or "")
    after_sop = counts()
    if after_sop["sop_templates"] != base["sop_templates"] + 1:
        raise Task22JCheckError("SOP template count did not increment by one")
    if after_sop["sop_execution_records"] != base["sop_execution_records"]:
        raise Task22JCheckError("SOP conversion must not create SOP execution")
    check_status_and_detail(state, state.sop_artifact_id or "", "sop_template", sop["conversion_trace_id"])
    duplicate_counts = counts()
    duplicate = expect_already_converted(
        "duplicate SOP conversion",
        cga.request_json(
            "POST",
            f"/agents/artifacts/{state.sop_artifact_id}/convert",
            token=state.expert_token,
            payload={"target_type": "sop_template", "approval_id": state.sop_approval_id},
            timeout=30,
        ),
    )
    if counts() != duplicate_counts:
        raise Task22JCheckError(f"duplicate conversion changed formal counts: {duplicate}")

    approve(state, state.task_approval_id or "", "task draft")
    task = convert(state, state.task_artifact_id or "", "maintenance_task", state.task_approval_id or "")
    after_task = counts()
    if after_task["maintenance_tasks"] != after_sop["maintenance_tasks"] + 1:
        raise Task22JCheckError("maintenance task count did not increment by one")
    if after_task["device_maintenance_records"] != after_sop["device_maintenance_records"]:
        raise Task22JCheckError("task conversion must not create maintenance record")
    check_status_and_detail(state, state.task_artifact_id or "", "maintenance_task", task["conversion_trace_id"])

    expect_blocked(
        "viewer conversion blocked",
        cga.request_json(
            "POST",
            f"/agents/artifacts/{state.task_artifact_id}/convert",
            token=state.viewer_token,
            payload={"target_type": "maintenance_task", "approval_id": state.task_approval_id},
            timeout=30,
        ),
    )
    expect_blocked(
        "engineer conversion blocked",
        cga.request_json(
            "POST",
            f"/agents/artifacts/{state.task_artifact_id}/convert",
            token=state.engineer_token,
            payload={"target_type": "maintenance_task", "approval_id": state.task_approval_id},
            timeout=30,
        ),
    )

    expect_blocked(
        "convert knowledge contribution before approval",
        cga.request_json(
            "POST",
            f"/agents/artifacts/{state.contribution_artifact_id}/convert",
            token=state.expert_token,
            payload={"target_type": "knowledge_contribution", "approval_id": state.curator_approval_id},
            timeout=30,
        ),
    )
    approve(state, state.curator_approval_id or "", "knowledge curator draft")
    contribution = convert(
        state,
        state.contribution_artifact_id or "",
        "knowledge_contribution",
        state.curator_approval_id or "",
    )
    after_contribution = counts()
    if after_contribution["knowledge_contributions"] != after_task["knowledge_contributions"] + 1:
        raise Task22JCheckError("knowledge contribution count did not increment by one")
    if after_contribution["knowledge_documents"] != after_task["knowledge_documents"]:
        raise Task22JCheckError("knowledge contribution conversion must not create document")
    if after_contribution["knowledge_chunks"] != after_task["knowledge_chunks"]:
        raise Task22JCheckError("knowledge contribution conversion must not create chunks")
    check_status_and_detail(
        state,
        state.contribution_artifact_id or "",
        "knowledge_contribution",
        contribution["conversion_trace_id"],
    )

    kg = convert(state, state.kg_artifact_id or "", "kg_candidate", state.curator_approval_id or "")
    after_kg = counts()
    if after_kg["kg_extraction_runs"] != after_contribution["kg_extraction_runs"] + 1:
        raise Task22JCheckError("KG extraction run count did not increment by one")
    if after_kg["kg_candidates"] <= after_contribution["kg_candidates"]:
        raise Task22JCheckError("KG candidate conversion did not create candidates")
    if after_kg["kg_nodes"] != after_contribution["kg_nodes"] or after_kg["kg_edges"] != after_contribution["kg_edges"]:
        raise Task22JCheckError("KG candidate conversion must not create formal KG nodes or edges")
    check_status_and_detail(state, state.kg_artifact_id or "", "kg_candidate", kg["conversion_trace_id"])
    with SessionLocal() as db:
        conversion_rows = int(db.scalar(select(func.count()).select_from(AgentArtifactConversion)) or 0)
        succeeded_rows = int(
            db.scalar(
                select(func.count()).select_from(AgentArtifactConversion).where(
                    AgentArtifactConversion.conversion_status == "succeeded"
                )
            )
            or 0
        )
        event_rows = int(
            db.scalar(
                select(func.count()).select_from(AgentEventLog).where(
                    AgentEventLog.event_type == "draft_converted_to_formal_object"
                )
            )
            or 0
        )
    if conversion_rows < len(state.conversion_trace_ids) or succeeded_rows < len(state.conversion_trace_ids):
        raise Task22JCheckError("conversion table does not contain succeeded records for all conversions")
    if event_rows < len(state.conversion_trace_ids):
        raise Task22JCheckError("conversion event_log compatibility records are missing")
    record(state, "manual artifact conversions", "passed", f"trace_ids={len(state.conversion_trace_ids)} conversion_rows={conversion_rows}")


def check_no_package(state: State) -> None:
    if delivery_zip_snapshot() != state.zip_snapshot:
        raise Task22JCheckError("delivery zip snapshot changed during Task22J")
    record(state, "no delivery package changed", "passed", "zip snapshot unchanged")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed(state)
        ensure_users(state)
        create_device(state)
        upload_media(state)
        create_sop_and_task_sources(state)
        create_curator_source(state)
        check_approval_boundaries(state)
        check_conversions(state)
        check_no_package(state)
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] Task22J artifact conversion flow: {exc}")
        return 1
    print(
        "task22j_artifact_conversion_flow_result "
        f"checks={len(state.results)} device_id={state.device_id} media_id={state.media_id} "
        f"conversion_traces={','.join(state.conversion_trace_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
