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


API_BASE_URL = os.getenv("TASK22G_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("TASK22G_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22G_{RUN_ID}"
TEST_PASSWORD = os.getenv("TASK22G_TEST_PASSWORD", "Task22G_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("TASK22G_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("TASK22G_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class Task22GCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    engineer_token: str | None = None
    expert_token: str | None = None
    viewer_token: str | None = None
    media_id: str | None = None
    dry_run_id: str | None = None
    mock_run_id: str | None = None
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
        raise Task22GCheckError(
            f"{label} failed: http={status}, code={body.get('code')}, message={body.get('message')}"
        )
    return body.get("data")


def expect_forbidden(label: str, response: tuple[int, dict[str, Any]]) -> None:
    status, body = response
    if status in {401, 403} or (isinstance(body.get("code"), int) and body.get("code") not in {0, 200}):
        return
    raise Task22GCheckError(f"{label} should be forbidden, got http={status}, code={body.get('code')}")


def ensure_seed(state: State) -> None:
    if seed_agent_runtime() != 0:
        raise Task22GCheckError("seed_agent_runtime.py failed")
    if seed_external_api_providers() != 0 or seed_external_api_providers() != 0:
        raise Task22GCheckError("seed_external_api_providers.py failed or is not idempotent")
    record(state, "seed agent runtime and external providers", "passed", "idempotent=true")


def ensure_users(state: State) -> None:
    state.admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        cga.ensure_user(state.admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        setattr(state, f"{role}_token", token)
    record(state, "login admin/engineer/expert/viewer", "passed", "tokens acquired")


def upload_media(state: State) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} Huawei SUN2000 inverter alarm screen for multimodal agent"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
        ("fault_type", "low_insulation_resistance"),
        ("alarm_code", f"{MARKER}_ALARM"),
    ]
    body, content_type = cga.multipart_body(fields, "file", f"{MARKER}_pv_inverter_alarm.png", cga.SAMPLE_PNG, "image/png")
    response = cga.request_json(
        "POST",
        "/media/upload",
        token=state.engineer_token,
        body=body,
        content_type=content_type,
        timeout=60,
    )
    media = api_data("upload Task22G media", response)
    state.media_id = str(media.get("media_id") or media.get("id"))
    if not state.media_id:
        raise Task22GCheckError("media upload did not return media_id")
    record(state, "upload Task22G media", "passed", state.media_id)


def create_agent_run(
    state: State,
    *,
    token: str,
    mock_run: bool,
    label: str,
) -> dict[str, Any]:
    payload = {
        "agent_code": "multimodal_evidence_agent",
        "input_text": (
            f"{MARKER} 现场逆变器屏幕显示绝缘阻抗异常，柜体附近有潮湿痕迹，"
            "请生成多模态证据摘要、安全复核清单和证据链。"
        ),
        "media_ids": [state.media_id],
        "tools": ["media_lookup", "media_ocr", "media_mimo_analysis", "safety_guard"],
        "context": {
            "agent_code": "multimodal_evidence_agent",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "fault_type": "low_insulation_resistance",
            "alarm_code": f"{MARKER}_ALARM",
            "source": "task22g_check",
        },
        "tool_inputs": {
            "media_ocr": {"mock_run": mock_run, "capability": "ocr"},
            "media_mimo_analysis": {
                "mock_run": mock_run,
                "capability": "fault_scene_analysis",
                "analysis_type": "fault_scene",
            },
            "safety_guard": {"source": "task22g_check"},
        },
        "dry_run": not mock_run,
        "mock_run": mock_run,
    }
    run = api_data(label, cga.request_json("POST", "/agents/runs", token=token, payload=payload, timeout=90))
    run_id = str(run.get("run_id"))
    if not run_id:
        raise Task22GCheckError(f"{label} did not return run_id")
    return get_timeline(state, run_id, token=token)


def get_timeline(state: State, run_id: str, *, token: str) -> dict[str, Any]:
    timeline = api_data(
        f"timeline {run_id}",
        cga.request_json("GET", f"/agents/runs/{run_id}/timeline", token=token, timeout=30),
    )
    for key in ("run", "steps", "tool_calls", "artifacts", "approvals", "events"):
        if key not in timeline:
            raise Task22GCheckError(f"timeline missing {key}")
    return timeline


def assert_timeline(timeline: dict[str, Any], *, mock_run: bool) -> None:
    steps = timeline.get("steps") or []
    names = [item.get("step_name") for item in steps]
    expected = [
        "validate_input",
        "load_media_context",
        "run_ocr_evidence",
        "run_visual_analysis",
        "run_safety_guard",
        "build_evidence_summary",
        "create_evidence_links",
        "finalize_run",
    ]
    missing = [item for item in expected if item not in names]
    if missing:
        raise Task22GCheckError(f"missing orchestration steps: {missing}")
    if any(not item.get("reasoning_summary") for item in steps):
        raise Task22GCheckError("all steps must include reasoning_summary")

    calls = {item.get("tool_name"): item for item in timeline.get("tool_calls") or []}
    for tool in ("media_lookup", "media_ocr", "media_mimo_analysis", "safety_guard"):
        if tool not in calls:
            raise Task22GCheckError(f"missing tool call {tool}")
    if calls["safety_guard"].get("status") != "succeeded":
        raise Task22GCheckError("safety_guard should succeed")
    if not mock_run:
        for tool in ("media_ocr", "media_mimo_analysis"):
            if calls[tool].get("status") not in {"blocked", "succeeded"}:
                raise Task22GCheckError(f"{tool} should be blocked or read existing evidence")

    artifacts = {item.get("artifact_type"): item for item in timeline.get("artifacts") or []}
    for artifact_type in ("multimodal_evidence_summary", "safety_checklist", "evidence_trace_summary"):
        if artifact_type not in artifacts:
            raise Task22GCheckError(f"missing artifact {artifact_type}")
    summary = artifacts["multimodal_evidence_summary"].get("content_json") or {}
    checklist = artifacts["safety_checklist"].get("content_json") or {}
    trace = artifacts["evidence_trace_summary"].get("content_json") or {}
    if not summary.get("requires_human_review") or summary.get("external_api_called") is not False:
        raise Task22GCheckError("multimodal evidence summary boundary fields are invalid")
    if not checklist.get("must_do") or not any("断" in str(item) for item in checklist.get("must_do", [])):
        raise Task22GCheckError("safety checklist must include power isolation items")
    if not trace.get("evidence_link_ids"):
        raise Task22GCheckError("trace summary must include evidence_link_ids")

    final_answer = str((timeline.get("run") or {}).get("final_answer") or "")
    if "external_api_called=false" not in final_answer:
        raise Task22GCheckError("final_answer must state external_api_called=false")
    if mock_run and ("mock" not in final_answer.lower() and "Mocked" not in final_answer):
        raise Task22GCheckError("mock-run final_answer must mention mocked result")
    if not mock_run and ("Blocked" not in final_answer and "blocked" not in final_answer):
        raise Task22GCheckError("dry-run final_answer must mention blocked boundary")


def check_dry_run(state: State) -> None:
    timeline = create_agent_run(state, token=state.engineer_token or "", mock_run=False, label="engineer dry-run agent")
    state.dry_run_id = timeline["run"]["run_id"]
    assert_timeline(timeline, mock_run=False)
    record(state, "engineer dry-run multimodal evidence agent", "passed", state.dry_run_id)


def check_mock_run(state: State) -> None:
    timeline = create_agent_run(state, token=state.expert_token or "", mock_run=True, label="expert mock-run agent")
    state.mock_run_id = timeline["run"]["run_id"]
    assert_timeline(timeline, mock_run=True)
    artifacts = timeline.get("artifacts") or []
    summary = next(item for item in artifacts if item.get("artifact_type") == "multimodal_evidence_summary")
    if not (summary.get("content_json") or {}).get("mocked"):
        raise Task22GCheckError("mock-run summary should be mocked=true")
    record(state, "expert mock-run multimodal evidence agent", "passed", state.mock_run_id)


def check_mocked_results_readable(state: State) -> None:
    timeline = create_agent_run(state, token=state.engineer_token or "", mock_run=False, label="engineer reads mocked evidence")
    calls = {item.get("tool_name"): item for item in timeline.get("tool_calls") or []}
    ocr_data = ((calls.get("media_ocr") or {}).get("output_json") or {}).get("data") or {}
    mimo_data = ((calls.get("media_mimo_analysis") or {}).get("output_json") or {}).get("data") or {}
    if not ocr_data.get("ocr_context"):
        raise Task22GCheckError("engineer dry-run did not read mocked OCR result")
    if not mimo_data.get("analyses"):
        raise Task22GCheckError("engineer dry-run did not read mocked AI analysis")
    record(state, "mocked evidence reused by agent tools", "passed", timeline["run"]["run_id"])


def check_viewer_blocked(state: State) -> None:
    payload = {
        "agent_code": "multimodal_evidence_agent",
        "input_text": "viewer should be blocked",
        "media_ids": [state.media_id],
        "tools": ["media_lookup"],
        "dry_run": True,
    }
    expect_forbidden(
        "viewer create multimodal evidence run",
        cga.request_json("POST", "/agents/runs", token=state.viewer_token, payload=payload, timeout=20),
    )
    record(state, "viewer create agent run blocked", "passed", "403 or business error")


def check_logs_and_no_package(state: State) -> None:
    logs = api_data(
        "external API logs",
        cga.request_json("GET", "/external-apis/logs?page=1&page_size=50", token=state.viewer_token, timeout=30),
    )
    raw = json.dumps(logs, ensure_ascii=False)
    forbidden_tokens = ["Authorization", "Bearer ", "MIMO_API_KEY", "CLOUD_LLM_API_KEY", "base64,", "\\storage\\uploads"]
    leaked = [item for item in forbidden_tokens if item in raw]
    if leaked:
        raise Task22GCheckError(f"external API logs leaked sensitive fields: {leaked}")
    after = delivery_zip_snapshot()
    if after != state.zip_snapshot:
        raise Task22GCheckError("delivery zip snapshot changed during Task22G check")
    record(state, "external logs sanitized and no delivery zip", "passed", f"zip_count={len(after)}")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed(state)
        ensure_users(state)
        upload_media(state)
        check_dry_run(state)
        check_mock_run(state)
        check_mocked_results_readable(state)
        check_viewer_blocked(state)
        check_logs_and_no_package(state)
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] Task22G multimodal evidence agent flow: {exc}")
        return 1
    print(
        "task22g_multimodal_evidence_agent_flow_result "
        f"checks={len(state.results)} media_id={state.media_id} dry_run_id={state.dry_run_id} mock_run_id={state.mock_run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
