from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID
from urllib import error, request

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import check_global_acceptance as cga  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.system import User  # noqa: E402
from app.schemas.multimodal_evidence import MediaAIAnalysisCreate  # noqa: E402
from app.services.multimodal_evidence_service import MultimodalEvidenceService  # noqa: E402
from seed_external_api_providers import main as seed_external_api_providers  # noqa: E402


API_BASE_URL = os.getenv("MULTIMODAL_EVIDENCE_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
RUN_ID = os.getenv("MULTIMODAL_EVIDENCE_RUN_ID", time.strftime("%Y%m%d%H%M%S"))
MARKER = f"Task22D_{RUN_ID}"
TEST_PASSWORD = os.getenv("MULTIMODAL_EVIDENCE_TEST_PASSWORD", "Task22D_pass123")

cga.API_BASE_URL = API_BASE_URL
cga.APP_BASE_URL = API_BASE_URL[:-4] if API_BASE_URL.endswith("/api") else API_BASE_URL
cga.ADMIN_USERNAME = os.getenv("MULTIMODAL_EVIDENCE_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
cga.ADMIN_PASSWORD = os.getenv("MULTIMODAL_EVIDENCE_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
cga.TEST_PASSWORD = TEST_PASSWORD
cga.RUN_ID = RUN_ID
cga.MARKER = MARKER


class MultimodalEvidenceCheckError(AssertionError):
    pass


@dataclass(slots=True)
class State:
    admin_token: str | None = None
    engineer_token: str | None = None
    expert_token: str | None = None
    viewer_token: str | None = None
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    media_id: str | None = None
    ocr_job_id: str | None = None
    mimo_job_id: str | None = None
    analysis_id: str | None = None
    evidence_link_id: str | None = None
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
        raise MultimodalEvidenceCheckError(
            f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}"
        )
    return response.get("data")


def expect_forbidden(label: str, status: int, response: dict[str, Any]) -> None:
    code = response.get("code")
    if status in (401, 403) or (isinstance(code, int) and code not in (0, 200)):
        return
    raise MultimodalEvidenceCheckError(f"{label} should be forbidden, got http={status}, code={code}")


def ensure_seed(state: State) -> None:
    first = seed_external_api_providers()
    second = seed_external_api_providers()
    if first != 0 or second != 0:
        raise MultimodalEvidenceCheckError("external API provider seed did not return success twice")
    record(state, "external provider seed", "passed", "idempotent=true")


def ensure_users(state: State) -> None:
    admin_token, admin_user = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    state.admin_token = admin_token
    state.users["admin"] = admin_user
    for role in ("engineer", "expert", "viewer"):
        username = f"{MARKER}_{role}"
        user = cga.ensure_user(admin_token, username, role, f"{MARKER} {role}")
        token, _ = cga.login(username, TEST_PASSWORD)
        state.users[role] = user
        setattr(state, f"{role}_token", token)
    record(state, "login admin/engineer/expert/viewer", "passed", "tokens acquired")


def upload_test_media(state: State) -> None:
    fields = [
        ("media_type", "fault_image"),
        ("description", f"{MARKER} PV inverter alarm screen placeholder"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
        ("fault_type", "alarm_code_query"),
        ("alarm_code", "ALM-22D"),
    ]
    body, content_type = cga.multipart_body(fields, "file", f"{MARKER}_sample.png", cga.SAMPLE_PNG, "image/png")
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
        raise MultimodalEvidenceCheckError("media upload did not return media_id")
    record(state, "Task22D media upload", "passed", state.media_id)


def check_jobs(state: State) -> None:
    if not state.media_id:
        raise MultimodalEvidenceCheckError("media_id missing")
    status, response = request_json(
        "POST",
        f"/multimodal/media/{state.media_id}/jobs",
        token=state.engineer_token,
        payload={"job_type": "ocr", "input_summary": {"marker": MARKER, "image_base64": "SHOULD_BE_OMITTED"}},
    )
    ocr_job = api_data("create OCR job", status, response)
    state.ocr_job_id = ocr_job["id"]
    if ocr_job.get("status") != "blocked":
        raise MultimodalEvidenceCheckError(f"OCR job should be blocked, got {ocr_job.get('status')}")
    record(state, "create OCR blocked job", "passed", state.ocr_job_id)

    status, response = request_json(
        "POST",
        f"/multimodal/media/{state.media_id}/jobs",
        token=state.engineer_token,
        payload={"job_type": "multimodal_analysis", "input_summary": {"marker": MARKER}},
    )
    mimo_job = api_data("create multimodal job", status, response)
    state.mimo_job_id = mimo_job["id"]
    if mimo_job.get("status") != "blocked":
        raise MultimodalEvidenceCheckError(f"multimodal job should be blocked, got {mimo_job.get('status')}")
    record(state, "create multimodal blocked job", "passed", state.mimo_job_id)

    status, response = request_json("GET", f"/multimodal/media/{state.media_id}/jobs", token=state.viewer_token)
    jobs = api_data("list jobs", status, response)
    if jobs.get("total", 0) < 2:
        raise MultimodalEvidenceCheckError("job list did not include created jobs")
    record(state, "GET jobs by media", "passed", f"total={jobs.get('total')}")

    status, response = request_json("GET", f"/multimodal/jobs/{state.ocr_job_id}", token=state.viewer_token)
    api_data("job detail", status, response)
    record(state, "GET job detail", "passed", state.ocr_job_id)


def check_empty_result_lists(state: State) -> None:
    if not state.media_id:
        raise MultimodalEvidenceCheckError("media_id missing")
    status, response = request_json("GET", f"/multimodal/media/{state.media_id}/ocr-results", token=state.viewer_token)
    api_data("OCR results list", status, response)
    record(state, "GET OCR results", "passed", "readable")
    status, response = request_json("GET", f"/multimodal/media/{state.media_id}/analyses", token=state.viewer_token)
    api_data("analyses list", status, response)
    record(state, "GET analyses", "passed", "readable")


def create_manual_analysis(state: State) -> None:
    if not state.media_id:
        raise MultimodalEvidenceCheckError("media_id missing")
    db = SessionLocal()
    try:
        expert = db.get(User, UUID(str(state.users["expert"]["id"])))
        if not expert:
            raise MultimodalEvidenceCheckError("expert user not found in database")
        payload = MediaAIAnalysisCreate(
            media_id=state.media_id,
            job_id=state.mimo_job_id,
            provider_code="manual",
            provider_name="Task22D manual review seed",
            model_name="rule_based_manual_fixture",
            analysis_type="fault_scene",
            summary=f"{MARKER} manual analysis fixture for PV inverter alarm screen review.",
            detected_text="ALM-22D",
            detected_alarm_codes_json=["ALM-22D"],
            visual_findings_json=[{"finding": "alarm screen placeholder", "source": "manual_fixture"}],
            possible_faults_json=[{"fault_type": "alarm_code_query", "confidence": 0.5}],
            safety_risks_json=[{"risk": "electrical isolation must be confirmed before inspection"}],
            recommended_actions_json=[{"action": "verify inverter alarm code and inspect DC/AC status"}],
            limitations_json=["manual fixture only; no real image understanding was performed"],
            confidence=0.5,
            raw_response_json={"marker": MARKER, "external_api_called": False},
        )
        analysis = MultimodalEvidenceService(db).create_manual_ai_analysis_for_test_or_review(payload, expert)
        state.analysis_id = str(analysis.id)
    finally:
        db.close()
    record(state, "create manual AI analysis through service", "passed", state.analysis_id or "")


def check_review_and_links(state: State) -> None:
    if not state.analysis_id or not state.media_id:
        raise MultimodalEvidenceCheckError("analysis_id or media_id missing")
    status, response = request_json(
        "POST",
        f"/multimodal/analyses/{state.analysis_id}/review",
        token=state.expert_token,
        payload={"human_review_status": "accepted", "review_comment": f"{MARKER} accepted for evidence center test"},
    )
    reviewed = api_data("expert review analysis", status, response)
    if reviewed.get("human_review_status") != "accepted":
        raise MultimodalEvidenceCheckError("expert review did not set accepted status")
    record(state, "expert review analysis accepted", "passed", state.analysis_id)

    status, response = request_json(
        "POST",
        f"/multimodal/analyses/{state.analysis_id}/review",
        token=state.viewer_token,
        payload={"human_review_status": "rejected", "review_comment": "viewer should be blocked"},
    )
    expect_forbidden("viewer review analysis", status, response)
    record(state, "viewer review blocked", "passed", f"http={status}")

    status, response = request_json(
        "POST",
        "/multimodal/evidence-links",
        token=state.engineer_token,
        payload={
            "media_id": state.media_id,
            "analysis_id": state.analysis_id,
            "source_type": "agent_run",
            "source_id": f"{MARKER}_agent_run_placeholder",
            "relation_type": "supports",
        },
    )
    link = api_data("create evidence link", status, response)
    state.evidence_link_id = link["id"]
    record(state, "create evidence link", "passed", state.evidence_link_id)

    status, response = request_json(
        "GET",
        f"/multimodal/evidence-links?media_id={state.media_id}",
        token=state.viewer_token,
    )
    links = api_data("list evidence links", status, response)
    if links.get("total", 0) < 1:
        raise MultimodalEvidenceCheckError("evidence link list is empty")
    record(state, "GET evidence links", "passed", f"total={links.get('total')}")


def check_summary_and_agent_tools(state: State) -> None:
    if not state.media_id:
        raise MultimodalEvidenceCheckError("media_id missing")
    status, response = request_json("GET", f"/multimodal/media/{state.media_id}/summary", token=state.viewer_token)
    summary = api_data("media multimodal summary", status, response)
    if len(summary.get("jobs", [])) < 2 or len(summary.get("analyses", [])) < 1:
        raise MultimodalEvidenceCheckError("summary did not include jobs and analysis")
    record(state, "GET media multimodal summary", "passed", "jobs and analyses present")

    payload = {
        "agent_code": "multimodal_evidence_agent",
        "input_text": "Read multimodal evidence center context for a PV inverter alarm screen.",
        "media_ids": [state.media_id],
        "tools": ["media_lookup", "media_ocr", "media_mimo_analysis"],
        "context": {
            "agent_code": "multimodal_evidence_agent",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
        },
        "dry_run": True,
    }
    status, response = request_json("POST", "/agents/runs", token=state.engineer_token, payload=payload, timeout=60)
    run = api_data("agent run with media tools", status, response)
    state.agent_run_id = run["run_id"]
    status, response = request_json("GET", f"/agents/runs/{state.agent_run_id}", token=state.engineer_token)
    detail = api_data("agent detail", status, response)
    calls = {item["tool_name"]: item for item in detail.get("tool_calls", [])}
    lookup_output = (calls.get("media_lookup") or {}).get("output_json") or {}
    if not ((lookup_output.get("data") or {}).get("multimodal_summaries")):
        raise MultimodalEvidenceCheckError("media_lookup did not include multimodal summary")
    mimo_output = (calls.get("media_mimo_analysis") or {}).get("output_json") or {}
    mimo_data = mimo_output.get("data") or {}
    if mimo_output.get("status") not in {"succeeded", "waiting_approval"} or not mimo_data.get("analyses"):
        raise MultimodalEvidenceCheckError("media_mimo_analysis did not read accepted analysis")
    ocr_output = (calls.get("media_ocr") or {}).get("output_json") or {}
    if ocr_output.get("status") not in {"blocked", "succeeded"}:
        raise MultimodalEvidenceCheckError("media_ocr did not return blocked or succeeded")
    record(state, "agent media tools read evidence center", "passed", state.agent_run_id)


def check_external_logs_and_no_package(state: State) -> None:
    status, response = request_json(
        "GET",
        "/external-apis/logs?page=1&page_size=20",
        token=state.viewer_token,
    )
    logs = api_data("external API logs", status, response)
    items = logs.get("items", [])
    if not items:
        raise MultimodalEvidenceCheckError("external API logs are empty")
    raw = json.dumps(items, ensure_ascii=False)
    if "SHOULD_BE_OMITTED" in raw:
        raise MultimodalEvidenceCheckError("external API log leaked base64/input marker")
    record(state, "external_api_call_logs blocked/dry-run", "passed", f"items={len(items)}")

    after = delivery_zip_snapshot()
    if after != state.zip_snapshot:
        raise MultimodalEvidenceCheckError("delivery zip snapshot changed during Task 22D check")
    record(state, "no delivery zip generated", "passed", f"zip_count={len(after)}")


def main() -> int:
    state = State(zip_snapshot=delivery_zip_snapshot())
    try:
        ensure_seed(state)
        ensure_users(state)
        upload_test_media(state)
        check_jobs(state)
        check_empty_result_lists(state)
        create_manual_analysis(state)
        check_review_and_links(state)
        check_summary_and_agent_tools(state)
        check_external_logs_and_no_package(state)
    except Exception as exc:  # noqa: BLE001
        print(f"[failed] multimodal evidence flow: {exc}")
        return 1
    print(
        "multimodal_evidence_flow_result "
        f"checks={len(state.results)} media_id={state.media_id} analysis_id={state.analysis_id} "
        f"run_id={state.agent_run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
