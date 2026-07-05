from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models import AgentApproval, AgentArtifact, AgentArtifactConversion, AgentEventLog, AgentRun, SOPTemplate  # noqa: E402
from seed_agent_runtime import main as seed_agent_runtime  # noqa: E402
from seed_external_api_providers import main as seed_external_api_providers  # noqa: E402


API_BASE_URL = os.getenv("TASK24E_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("TASK24E_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task24E_{RUN_ID}"
TEST_PASSWORD = os.getenv("TASK24E_TEST_PASSWORD", "Task24E_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("TASK24E_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("TASK24E_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class Task24ECheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str = ""
    engineer_token: str = ""
    expert_token: str = ""
    viewer_token: str = ""
    engineer_user_id: str = ""
    expert_user_id: str = ""
    sop_artifact_id: str = ""
    sop_approval_id: str = ""
    rejected_artifact_id: str = ""
    rejected_approval_id: str = ""
    pending_artifact_id: str = ""
    pending_approval_id: str = ""
    failed_artifact_id: str = ""
    failed_approval_id: str = ""
    results: list[dict[str, str]] = field(default_factory=list)


def record(state: State, name: str, status: str, notes: str = "") -> None:
    state.results.append({"name": name, "status": status, "notes": notes})
    print(f"[{status}] {name}: {notes}")


def api_data(label: str, response: tuple[int, dict[str, Any]]) -> Any:
    status, body = response
    if status >= 400 or body.get("code") not in (0, 200):
        raise Task24ECheckError(f"{label} failed: http={status}, code={body.get('code')}, message={body.get('message')}")
    return body.get("data")


def expect_blocked(label: str, response: tuple[int, dict[str, Any]]) -> None:
    status, body = response
    code_text = str(body.get("code"))
    if status in {401, 403} or code_text.startswith(("400", "401", "403")):
        return
    raise Task24ECheckError(f"{label} should be blocked, got http={status}, code={body.get('code')}, body={body}")


def ensure_seed(state: State) -> None:
    if seed_agent_runtime() != 0:
        raise Task24ECheckError("seed_agent_runtime.py failed")
    if seed_external_api_providers() != 0:
        raise Task24ECheckError("seed_external_api_providers.py failed")
    record(state, "seed runtime and providers", "passed", "idempotent=true")


def ensure_users(state: State) -> None:
    state.admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    for role in ("engineer", "expert", "viewer"):
        user = cga.ensure_user(state.admin_token, f"{MARKER}_{role}", role, f"{MARKER} {role}")
        token, _ = cga.login(user["username"], TEST_PASSWORD)
        setattr(state, f"{role}_token", token)
        if role in {"engineer", "expert"}:
            setattr(state, f"{role}_user_id", user["id"])
    record(state, "login admin/engineer/expert/viewer", "passed", "tokens acquired")


def create_sop_draft(state: State, suffix: str) -> tuple[str, str]:
    payload = {
        "agent_code": "sop_planner_agent",
        "input_text": f"{MARKER} {suffix} SUN2000 low insulation SOP conversion test.",
        "tools": ["device_lookup", "knowledge_search", "kg_business_context", "sop_generator", "safety_guard"],
        "context": {
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "fault_type": "low_insulation_resistance",
            "alarm_code": f"{MARKER}_{suffix}_ALARM",
            "source": "task24e_concurrency",
        },
        "dry_run": True,
        "mock_run": False,
    }
    run = api_data("create sop draft run", cga.request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload, timeout=90))
    timeline = api_data("get sop draft timeline", cga.request_json("GET", f"/agents/runs/{run['run_id']}/timeline", token=state.engineer_token, timeout=30))
    artifact = next(item for item in timeline["artifacts"] if item["artifact_type"] == "sop_draft")
    approval = next(item for item in timeline["approvals"] if item["approval_type"] == "sop_draft_review")
    return artifact["id"], approval["id"]


def approve(state: State, approval_id: str) -> None:
    data = api_data(
        "approve draft",
        cga.request_json(
            "POST",
            f"/agents/approvals/{approval_id}/approve",
            token=state.expert_token,
            payload={"review_comment": f"{MARKER} approved."},
            timeout=30,
        ),
    )
    if data.get("status") != "approved":
        raise Task24ECheckError("approval did not become approved")


def reject(state: State, approval_id: str) -> None:
    data = api_data(
        "reject draft",
        cga.request_json(
            "POST",
            f"/agents/approvals/{approval_id}/reject",
            token=state.expert_token,
            payload={"review_comment": f"{MARKER} rejected."},
            timeout=30,
        ),
    )
    if data.get("status") != "rejected":
        raise Task24ECheckError("approval did not become rejected")


def convert_request(token: str, artifact_id: str, approval_id: str) -> tuple[int, dict[str, Any]]:
    return cga.request_json(
        "POST",
        f"/agents/artifacts/{artifact_id}/convert",
        token=token,
        payload={
            "target_type": "sop_template",
            "approval_id": approval_id,
            "comment": f"{MARKER} concurrent conversion.",
        },
        timeout=60,
    )


def count_sop_templates() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(SOPTemplate)) or 0)


def conversions_for_artifact(artifact_id: str) -> list[AgentArtifactConversion]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(AgentArtifactConversion).where(
                    AgentArtifactConversion.source_artifact_id == UUID(artifact_id),
                    AgentArtifactConversion.target_type == "sop_template",
                )
            )
        )


def check_unique_constraint(state: State) -> None:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                select conname
                from pg_constraint
                where conname = 'uq_agent_artifact_conversions_artifact_target'
                """
            )
        ).all()
    if not rows:
        raise Task24ECheckError("unique constraint uq_agent_artifact_conversions_artifact_target not found")
    record(state, "database unique constraint", "passed", "source_artifact_id + target_type")


def check_concurrent_conversion(state: State) -> None:
    before_sop = count_sop_templates()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(convert_request, state.expert_token, state.sop_artifact_id, state.sop_approval_id)
            for _ in range(5)
        ]
        responses = [future.result() for future in futures]

    successful_targets: list[str] = []
    already_or_conflict = 0
    for response in responses:
        status, body = response
        if status >= 400 or body.get("code") not in {0, 200}:
            code_text = str(body.get("code"))
            if code_text.startswith(("400", "409")):
                already_or_conflict += 1
                continue
            raise Task24ECheckError(f"unexpected concurrent response: http={status}, body={body}")
        data = body.get("data") or {}
        if data.get("status") in {"already_converted", "conversion_in_progress"} or data.get("already_converted"):
            already_or_conflict += 1
        elif data.get("conversion_status") == "succeeded" or data.get("status") == "succeeded":
            successful_targets.append(str(data.get("target_id")))
        else:
            raise Task24ECheckError(f"unexpected concurrent success payload: {data}")

    rows = conversions_for_artifact(state.sop_artifact_id)
    succeeded = [item for item in rows if item.conversion_status == "succeeded"]
    after_sop = count_sop_templates()
    if len(rows) != 1 or len(succeeded) != 1:
        raise Task24ECheckError(f"expected exactly one conversion row and one succeeded row, got rows={len(rows)} succeeded={len(succeeded)}")
    if after_sop != before_sop + 1:
        raise Task24ECheckError(f"expected exactly one SOP template created, before={before_sop} after={after_sop}")
    if not succeeded[0].target_id:
        raise Task24ECheckError("succeeded conversion target_id is empty")
    if len(set(successful_targets)) > 1:
        raise Task24ECheckError(f"concurrent requests returned multiple target ids: {successful_targets}")

    history = api_data(
        "artifact conversion history",
        cga.request_json("GET", f"/agents/artifacts/{state.sop_artifact_id}/conversions", token=state.expert_token, timeout=30),
    )
    if not any(item.get("id") == str(succeeded[0].id) for item in history):
        raise Task24ECheckError("artifact history does not include succeeded conversion")
    events = event_count_for_trace(succeeded[0].conversion_trace_id)
    if events < 1:
        raise Task24ECheckError("conversion event_log compatibility record missing")
    record(
        state,
        "concurrent conversion idempotency",
        "passed",
        f"requests=5 conversion_rows=1 succeeded=1 duplicate_or_conflict={already_or_conflict}",
    )


def event_count_for_trace(trace_id: str) -> int:
    with SessionLocal() as db:
        return int(
            db.scalar(
                select(func.count()).select_from(AgentEventLog).where(
                    AgentEventLog.event_type == "draft_converted_to_formal_object",
                    AgentEventLog.payload_json.contains({"conversion_trace_id": trace_id}),
                )
            )
            or 0
        )


def create_failed_kg_artifact(state: State) -> None:
    with SessionLocal() as db:
        run = AgentRun(
            run_id=f"agent-{uuid4().hex}",
            agent_code="knowledge_curator_agent",
            user_id=UUID(state.engineer_user_id),
            status="succeeded",
            input_text=f"{MARKER} invalid KG candidate conversion",
            context_json={
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
            },
            requires_human_approval=True,
            approval_status="approved",
        )
        db.add(run)
        db.flush()
        artifact = AgentArtifact(
            run_id=run.run_id,
            artifact_type="kg_candidate_suggestion",
            title=f"{MARKER} invalid empty KG suggestion",
            content_json={"candidate_nodes": [], "candidate_edges": []},
            source_type="task24e",
        )
        db.add(artifact)
        db.flush()
        approval = AgentApproval(
            run_id=run.run_id,
            approval_type="knowledge_contribution_draft_review",
            requested_action="review_kg_candidate_suggestion",
            payload_json={"source_artifact_id": str(artifact.id)},
            status="approved",
            requested_by=UUID(state.engineer_user_id),
            reviewed_by=UUID(state.expert_user_id),
        )
        db.add(approval)
        db.commit()
        db.refresh(artifact)
        db.refresh(approval)
        state.failed_artifact_id = str(artifact.id)
        state.failed_approval_id = str(approval.id)


def check_role_and_approval_boundaries(state: State) -> None:
    expect_blocked("viewer conversion blocked", convert_request(state.viewer_token, state.sop_artifact_id, state.sop_approval_id))
    expect_blocked("engineer conversion blocked", convert_request(state.engineer_token, state.sop_artifact_id, state.sop_approval_id))

    state.pending_artifact_id, state.pending_approval_id = create_sop_draft(state, "pending")
    expect_blocked("pending approval conversion blocked", convert_request(state.expert_token, state.pending_artifact_id, state.pending_approval_id))

    state.rejected_artifact_id, state.rejected_approval_id = create_sop_draft(state, "rejected")
    reject(state, state.rejected_approval_id)
    expect_blocked("rejected approval conversion blocked", convert_request(state.expert_token, state.rejected_artifact_id, state.rejected_approval_id))
    record(state, "role and approval boundaries", "passed", "viewer/engineer/pending/rejected blocked")


def check_failed_conversion_record(state: State) -> None:
    create_failed_kg_artifact(state)
    response = cga.request_json(
        "POST",
        f"/agents/artifacts/{state.failed_artifact_id}/convert",
        token=state.expert_token,
        payload={
            "target_type": "kg_candidate",
            "approval_id": state.failed_approval_id,
            "comment": f"{MARKER} failed conversion check",
        },
        timeout=30,
    )
    expect_blocked("invalid KG conversion failed", response)
    with SessionLocal() as db:
        conversion = db.scalar(
            select(AgentArtifactConversion).where(
                AgentArtifactConversion.source_artifact_id == UUID(state.failed_artifact_id),
                AgentArtifactConversion.target_type == "kg_candidate",
            )
        )
    if not conversion or conversion.conversion_status != "failed" or not conversion.error_message:
        raise Task24ECheckError("failed conversion record missing or incomplete")
    record(state, "failed conversion record", "passed", f"conversion_id={conversion.id}")


def main() -> int:
    state = State()
    try:
        ensure_seed(state)
        ensure_users(state)
        check_unique_constraint(state)
        state.sop_artifact_id, state.sop_approval_id = create_sop_draft(state, "concurrency")
        approve(state, state.sop_approval_id)
        check_concurrent_conversion(state)
        check_role_and_approval_boundaries(state)
        check_failed_conversion_record(state)
        output = {"status": "passed", "results": state.results}
        runtime_dir = ROOT_DIR / ".runtime" / "task24e"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "agent_conversion_concurrency_result.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] Task24E conversion concurrency flow: {exc}")
        return 1
    print(f"task24e_conversion_concurrency_flow_result checks={len(state.results)} artifact_id={state.sop_artifact_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
