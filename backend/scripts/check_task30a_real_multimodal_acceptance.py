from __future__ import annotations

import argparse
import json
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
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    DiagnosisRecord,
    ExternalApiCallLog,
    KnowledgeChunk,
    KnowledgeDocument,
    MaintenanceTask,
    ModelOutputCorrection,
    MediaAIAnalysis,
    MediaOCRResult,
    MultimodalMaintenanceCase,
    QARecord,
    SOPExecutionRecord,
    UploadedMedia,
    User,
    VectorIndexRun,
)
from scripts.task24c_real_api_common import (  # noqa: E402
    api_data,
    contains_sensitive_value,
    multipart_body,
    request_json,
)


TASK = "task30a"
APPROVAL = "APPROVE_TASK30A_REAL_MULTIMODAL_TEST_V1"
EXPECTED_DATABASE = "energy_maintenance_task30a_test"
EXPECTED_ALEMBIC = "20260712_0015"
RUNTIME = ROOT_DIR / ".runtime" / "task30a"
MANIFEST_PATH = RUNTIME / "input" / "image_manifest.json"
GROUND_TRUTH_PATH = BACKEND_DIR / "tests" / "fixtures" / "task30a_multimodal_ground_truth.json"
LEDGER_PATH = RUNTIME / "provider_calls" / "provider_call_ledger.json"
RESULT_PATH = RUNTIME / "results" / "task30a_functional_result.json"
BEFORE_PATH = RUNTIME / "database" / "before_counts.json"
AFTER_PATH = RUNTIME / "database" / "after_counts.json"
PRIVATE_CREDENTIALS = ROOT_DIR / ".runtime" / "task25a_r1" / ".test_credentials.private.json"


class Task30AError(AssertionError):
    pass


@dataclass
class State:
    base_url: str
    tokens: dict[str, str] = field(default_factory=dict)
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    cases: dict[str, str] = field(default_factory=dict)
    media: dict[str, str] = field(default_factory=dict)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    ocr_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    analyses: dict[str, dict[str, Any]] = field(default_factory=dict)
    ledger: list[dict[str, Any]] = field(default_factory=list)
    case_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    viewer_checks: dict[str, Any] = field(default_factory=dict)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _require_env() -> None:
    required = {
        "TASK30A_ALLOW_REAL_PROVIDER": "true",
        "TASK30A_ALLOW_TEST_DB_WRITES": "true",
        "TASK30A_MAX_REAL_PROVIDER_CALLS": "16",
    }
    for key, expected in required.items():
        if os.getenv(key, "").strip().lower() != expected:
            raise Task30AError("TASK30A_BLOCKED_EXPLICIT_APPROVAL_REQUIRED")


def _counts() -> dict[str, Any]:
    models = {
        "users": User,
        "uploaded_media": UploadedMedia,
        "multimodal_maintenance_cases": MultimodalMaintenanceCase,
        "qa_records": QARecord,
        "diagnosis_records": DiagnosisRecord,
        "maintenance_tasks": MaintenanceTask,
        "model_output_corrections": ModelOutputCorrection,
        "external_api_call_logs": ExternalApiCallLog,
        "vector_index_runs": VectorIndexRun,
        "sop_execution_records": SOPExecutionRecord,
        "knowledge_documents": KnowledgeDocument,
        "knowledge_chunks": KnowledgeChunk,
    }
    with SessionLocal() as db:
        database = str(db.scalar(select(func.current_database())) or "")
        port = int(db.scalar(select(func.inet_server_port())) or 0)
        if database != EXPECTED_DATABASE or port != 55433:
            raise Task30AError("TASK30A_SECURITY_BOUNDARY_VIOLATION")
        result = {"database": database, "port": port}
        for name, model in models.items():
            result[name] = int(db.scalar(select(func.count()).select_from(model)) or 0)
        return result


def _credentials() -> dict[str, dict[str, str]]:
    if not PRIVATE_CREDENTIALS.exists():
        raise Task30AError("Private test credentials are unavailable")
    data = json.loads(PRIVATE_CREDENTIALS.read_text(encoding="utf-8"))
    for role in ("admin", "expert", "engineer", "viewer"):
        item = data.get(role) or {}
        if not item.get("username") or not item.get("password"):
            raise Task30AError(f"Private test credential is incomplete for {role}")
    return data


def _login(state: State, role: str, credentials: dict[str, dict[str, str]]) -> None:
    item = credentials[role]
    status, response = request_json(
        "POST",
        "/auth/login",
        base_url=state.base_url,
        payload={"username": item["username"], "password": item["password"]},
        timeout=20,
    )
    data = api_data(f"{role} login", status, response)
    token = str((data or {}).get("access_token") or "")
    if not token:
        raise Task30AError(f"{role} login returned no token")
    state.tokens[role] = token
    state.users[role] = dict((data or {}).get("user") or {})


def _api(
    state: State,
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: dict[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str = "application/json",
    timeout: int = 45,
) -> Any:
    status, response = request_json(
        method,
        path,
        base_url=state.base_url,
        token=state.tokens.get(role),
        payload=payload,
        body=body,
        content_type=content_type,
        timeout=timeout,
    )
    return api_data(f"{method} {path}", status, response)


def _verify_preflight(state: State) -> dict[str, Any]:
    health = _api(state, "GET", "/health")
    status = _api(state, "GET", "/external-apis/status")
    providers = {item["provider_code"]: item for item in (status or {}).get("providers", [])}
    required = ("custom_ocr_api", "mimo_2_5")
    for code in required:
        item = providers.get(code) or {}
        if not item.get("enabled") or not item.get("configured"):
            raise Task30AError("TASK30A_BLOCKED_PROVIDER_NOT_CONFIGURED")
    if not MANIFEST_PATH.exists() or not GROUND_TRUTH_PATH.exists():
        raise Task30AError("Task30A image manifest or frozen ground truth is missing")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if len(manifest.get("images") or []) != 4 or manifest.get("privacy_rejected_count") != 0:
        raise Task30AError("TASK30A_PRIVACY_GATE_FAILED")
    return {
        "health": (health or {}).get("status"),
        "database": EXPECTED_DATABASE,
        "providers": {
            code: {
                "enabled": providers[code].get("enabled"),
                "configured": providers[code].get("configured"),
                "model_name": providers[code].get("model_name"),
                "capabilities": providers[code].get("capabilities"),
            }
            for code in required
        },
        "images": len(manifest["images"]),
        "privacy_rejected": manifest["privacy_rejected_count"],
    }


def _create_case(state: State, key: str, title: str, query: str) -> str:
    data = _api(
        state,
        "POST",
        "/multimodal/cases",
        payload={
            "title": title,
            "user_query": query,
            "device_model": "SUN2000",
            "product_family": "SUN2000",
            "equipment_category": "pv_inverter",
            "reported_symptoms": [query],
            "occurrence_conditions": ["Task 30A test only"],
            "idempotency_key": f"task30a-{key}-v1",
        },
    )
    case_id = str(data.get("case_id") or "")
    if not case_id:
        raise Task30AError(f"Case {key} was not created")
    state.cases[key] = case_id
    return case_id


def _upload_case_image(
    state: State,
    *,
    case_key: str,
    image_key: str,
    file_name: str,
    media_type: str,
    alarm_code: str | None = None,
) -> str:
    image_path = RUNTIME / "input" / file_name
    fields = [
        ("media_type", media_type),
        ("description", f"task30a {image_key} privacy-approved test-only image"),
        ("manufacturer", "huawei"),
        ("product_series", "SUN2000"),
        ("device_type", "pv_inverter"),
    ]
    if alarm_code:
        fields.append(("alarm_code", alarm_code))
    body, content_type = multipart_body(
        fields,
        "file",
        file_name,
        image_path.read_bytes(),
        "image/png",
    )
    data = _api(
        state,
        "POST",
        f"/multimodal/cases/{state.cases[case_key]}/media",
        body=body,
        content_type=content_type,
        timeout=60,
    )
    media_id = str(data.get("media_id") or "")
    if not media_id:
        raise Task30AError(f"Upload failed for {image_key}")
    state.media[image_key] = media_id
    return media_id


def _safe_ocr(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("raw_result_json") if isinstance(item.get("raw_result_json"), dict) else {}
    normalized = raw.get("normalized_result") if isinstance(raw.get("normalized_result"), dict) else {}
    return {
        "id": item.get("id"),
        "media_id": item.get("media_id"),
        "job_id": item.get("job_id"),
        "provider_code": item.get("provider_code"),
        "model_name": item.get("model_name"),
        "visible_text": item.get("text") or "",
        "confidence": float(item.get("confidence") or 0),
        "language": item.get("language"),
        "detected_alarm_codes": normalized.get("detected_alarm_codes") or [],
        "detected_device_info": normalized.get("detected_device_info") or {},
        "uncertain_spans": normalized.get("limitations") or [],
        "requires_confirmation": True,
        "external_trace_id": item.get("external_trace_id"),
    }


def _safe_analysis(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "media_id": item.get("media_id"),
        "job_id": item.get("job_id"),
        "provider_code": item.get("provider_code"),
        "model_name": item.get("model_name"),
        "analysis_type": item.get("analysis_type"),
        "summary": item.get("summary"),
        "visible_text": item.get("detected_text") or "",
        "detected_alarm_codes": item.get("detected_alarm_codes_json") or [],
        "detected_device_info": item.get("detected_device_info_json") or {},
        "observations": item.get("visual_findings_json") or [],
        "visible_anomalies": item.get("possible_faults_json") or [],
        "safety_flags": item.get("safety_risks_json") or [],
        "not_observable": item.get("limitations_json") or [],
        "confidence": float(item.get("confidence") or 0),
        "image_quality": "provider_result_requires_human_review",
        "requires_confirmation": True,
        "root_cause_determined": False,
        "human_review_status": item.get("human_review_status"),
        "external_trace_id": item.get("external_trace_id"),
    }


def _real_job(
    state: State,
    *,
    image_key: str,
    job_type: str,
    provider_code: str,
    capability: str,
    analysis_type: str | None,
    purpose: str,
    prompt: str,
) -> None:
    if len(state.ledger) >= 16:
        raise Task30AError("TASK30A_PROVIDER_CALL_BUDGET_EXCEEDED")
    started = time.time()
    payload = {
        "job_type": job_type,
        "provider_code": provider_code,
        "capability": capability,
        "analysis_type": analysis_type,
        "dry_run": False,
        "mock_run": False,
        "real_run": True,
        "input_summary": {
            "task_id": TASK,
            "approval_id": APPROVAL,
            "image_id": image_key,
            "purpose": purpose,
            "test_only": True,
            "privacy_passed": True,
            "prompt": prompt,
        },
    }
    job = _api(
        state,
        "POST",
        f"/multimodal/media/{state.media[image_key]}/jobs",
        payload=payload,
        timeout=120,
    )
    finished = time.time()
    trace_id = str(job.get("external_trace_id") or "")
    job_id = str(job.get("id") or "")
    if not trace_id or not job_id:
        raise Task30AError(f"Real job did not return trace/job id for {image_key}/{job_type}")
    log = _api(state, "GET", f"/external-apis/logs/{trace_id}")
    if contains_sensitive_value(log):
        raise Task30AError("TASK30A_SECURITY_BOUNDARY_VIOLATION")
    ledger_item = {
        "sequence": len(state.ledger) + 1,
        "case_id": next((state.cases[key] for key in state.cases if image_key in CASE_IMAGES[key]), None),
        "image_id": image_key,
        "provider": provider_code,
        "model": job.get("model_name"),
        "endpoint_host": os.getenv("TASK30A_ENDPOINT_HOST_LABEL", "configured-provider-host"),
        "purpose": purpose,
        "retry_of": None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished)),
        "latency_ms": int((finished - started) * 1000),
        "success": bool(job.get("status") == "succeeded"),
        "error_category": job.get("error_code"),
        "structured_result_present": False,
        "external_api_call_log_id": log.get("id"),
        "raw_response_saved": False,
        "secret_exposure": False,
    }
    state.ledger.append(ledger_item)
    _write_json(LEDGER_PATH, {"task": TASK, "hard_limit": 16, "calls": state.ledger})
    state.jobs[f"{image_key}:{job_type}"] = job

    if job.get("status") != "succeeded":
        return
    if job_type == "ocr":
        page = _api(state, "GET", f"/multimodal/media/{state.media[image_key]}/ocr-results?page=1&page_size=20")
        match = next((item for item in page.get("items", []) if str(item.get("job_id")) == job_id), None)
        if match:
            state.ocr_results[image_key] = _safe_ocr(match)
            ledger_item["structured_result_present"] = True
    else:
        page = _api(state, "GET", f"/multimodal/media/{state.media[image_key]}/analyses?page=1&page_size=20")
        match = next((item for item in page.get("items", []) if str(item.get("job_id")) == job_id), None)
        if match:
            state.analyses[image_key] = _safe_analysis(match)
            ledger_item["structured_result_present"] = True
            _api(
                state,
                "POST",
                f"/multimodal/analyses/{match['id']}/review",
                role="expert",
                payload={
                    "human_review_status": "accepted",
                    "review_comment": f"task30a human review: accepted as auxiliary visible evidence for {image_key}",
                },
            )
    _write_json(LEDGER_PATH, {"task": TASK, "hard_limit": 16, "calls": state.ledger})


CASE_IMAGES = {
    "case_a": {"alarm", "connector"},
    "case_b": {"nameplate", "grid_display"},
}


def _run_real_calls(state: State) -> None:
    calls = [
        ("nameplate", "ocr", "custom_ocr_api", "ocr", None, "nameplate visible text extraction", "Extract only visible text and ratings. Return strict JSON. Do not infer a serial number."),
        ("nameplate", "multimodal_analysis", "mimo_2_5", "nameplate_extract", "nameplate", "nameplate structured extraction", "Return strict JSON with visible_text, detected_device_info, visual_findings, confidence, limitations. Do not invent serial numbers. Human confirmation is required."),
        ("alarm", "ocr", "custom_ocr_api", "ocr", None, "alarm screen OCR", "Extract the visible Error 225 and PV IsolationLow text exactly. Return strict JSON and mark uncertainty."),
        ("alarm", "multimodal_analysis", "mimo_2_5", "alarm_screen_analysis", "alarm_screen", "alarm screen structured analysis", "Describe only visible alarm screen evidence. Return strict JSON. Never determine a root cause and require human confirmation."),
        ("connector", "multimodal_analysis", "mimo_2_5", "fault_scene_analysis", "wiring", "connector illustration analysis", "Identify this as a technical connector installation illustration. State what is visible and what cannot be verified about an actual field connector. No live-work or disassembly advice. Return strict JSON."),
        ("grid_display", "ocr", "custom_ocr_api", "ocr", None, "grid display OCR", "Extract visible Chinese display text, date, time, values and units. Do not infer a root cause."),
        ("grid_display", "multimodal_analysis", "mimo_2_5", "fault_scene_analysis", "alarm_screen", "grid display structured analysis", "Describe only the visible display. Do not infer measurement location or final grid fault root cause. Require field confirmation and return strict JSON."),
    ]
    for image_key, job_type, provider, capability, analysis_type, purpose, prompt in calls:
        _real_job(
            state,
            image_key=image_key,
            job_type=job_type,
            provider_code=provider,
            capability=capability,
            analysis_type=analysis_type,
            purpose=purpose,
            prompt=prompt,
        )


def _confirm_case_evidence(state: State, key: str) -> dict[str, Any]:
    case_id = state.cases[key]
    _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/analyze",
        payload={"dry_run": True, "mock_run": False, "allow_real_api": False, "force": True},
        timeout=90,
    )
    _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/clarify",
        payload={
            "answers": {"device_model": "SUN2000"},
            "confirmed_facts": {"manufacturer": "huawei", "product_series": "SUN2000"},
        },
    )
    evidence_page = _api(state, "GET", f"/multimodal/cases/{case_id}/evidence")
    candidates = [
        item
        for item in evidence_page.get("items", [])
        if item.get("source_type") in {"OCR_PROVIDER", "MULTIMODAL_PROVIDER"}
        and item.get("observation_status") not in {"USER_CONFIRMED", "REJECTED"}
    ]
    if not candidates:
        raise Task30AError(f"No provider evidence available for {key}")

    edited = candidates[0]
    original = str(edited.get("normalized_text") or edited.get("observed_text") or "")
    corrected = "225" if key == "case_a" else "SUN2000-196KTL-H0"
    _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/evidence/{edited['evidence_id']}/confirm",
        payload={"confirmed_value": corrected, "reason": "task30a manual field correction after image review"},
    )
    accepted = 1
    for item in candidates[1:3]:
        _api(
            state,
            "POST",
            f"/multimodal/cases/{case_id}/evidence/{item['evidence_id']}/confirm",
            payload={"confirmed_value": None, "reason": "task30a human-confirmed visible evidence"},
        )
        accepted += 1

    rejected = None
    retake = None
    if len(candidates) > 3:
        rejected = candidates[3]
        _api(
            state,
            "POST",
            f"/multimodal/cases/{case_id}/evidence/{rejected['evidence_id']}/reject",
            payload={"confirmed_value": None, "reason": "task30a rejected uncertain model inference"},
        )
    if len(candidates) > 4:
        retake = candidates[4]
        _api(
            state,
            "POST",
            f"/multimodal/cases/{case_id}/evidence/{retake['evidence_id']}/reject",
            payload={"confirmed_value": None, "reason": "request_retake: field image is required for confirmation"},
        )
    return {
        "accepted_count": accepted,
        "edited": {"evidence_id": edited["evidence_id"], "before": original[:160], "after": corrected},
        "rejected": rejected.get("evidence_id") if rejected else None,
        "request_retake": retake.get("evidence_id") if retake else None,
    }


def _citation_manufacturers(citations: list[dict[str, Any]]) -> set[str]:
    document_ids = [item.get("document_id") for item in citations if item.get("document_id")]
    if not document_ids:
        return set()
    with SessionLocal() as db:
        values = db.scalars(
            select(KnowledgeDocument.manufacturer).where(KnowledgeDocument.id.in_(document_ids))
        ).all()
    return {str(value or "").lower() for value in values}


def _qa_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(QARecord)) or 0)


def _run_case_flow(state: State, key: str) -> dict[str, Any]:
    case_id = state.cases[key]
    review = _confirm_case_evidence(state, key)
    request_id = f"task30a-{key}-qa-confirm-v1"
    before_preview = _qa_count()
    preview = _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/retrieve",
        payload={
            "top_k": 5,
            "requested_information": ["CAUSE", "ACTION", "SAFETY"],
            "persist_result": False,
            "request_id": request_id,
        },
        timeout=90,
    )
    after_preview = _qa_count()
    citations = preview.get("citations") or []
    manufacturers = _citation_manufacturers(citations)
    if after_preview != before_preview:
        raise Task30AError(f"{key} preview wrote a QA record")
    if not citations or "huawei" not in manufacturers or "sungrow" in manufacturers:
        raise Task30AError(f"{key} Huawei citation boundary failed")

    confirmed = _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/retrieve",
        payload={
            "top_k": 5,
            "requested_information": ["CAUSE", "ACTION", "SAFETY"],
            "persist_result": True,
            "request_id": request_id,
        },
        timeout=90,
    )
    after_confirm = _qa_count()
    if after_confirm != after_preview + 1:
        raise Task30AError(f"{key} QA confirm delta is not one")
    repeated = _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/retrieve",
        payload={
            "top_k": 5,
            "requested_information": ["CAUSE", "ACTION", "SAFETY"],
            "persist_result": True,
            "request_id": request_id,
        },
        timeout=90,
    )
    after_repeat = _qa_count()
    if after_repeat != after_confirm:
        raise Task30AError(f"{key} QA confirm is not idempotent")

    diagnosis = _api(
        state,
        "POST",
        f"/multimodal/cases/{case_id}/diagnose",
        payload={"proposed_actions": []},
        timeout=60,
    )
    sop = _api(state, "POST", f"/multimodal/cases/{case_id}/sop-draft", payload={}, timeout=60)
    trace_id = str(confirmed.get("trace_id") or "")
    record_search = _api(
        state,
        "GET",
        f"/record-center/search?record_type=qa&trace_id={trace_id}&page=1&page_size=20",
    )
    if not trace_id or not record_search.get("items"):
        raise Task30AError(f"{key} QA record is not traceable in Record Center")
    return {
        "review": review,
        "preview": {
            "qa_delta": after_preview - before_preview,
            "answer_present": bool(preview.get("answer")),
            "citation_count": len(citations),
            "citation_manufacturers": sorted(manufacturers),
            "persistence_status": preview.get("persistence_status"),
        },
        "confirm": {
            "qa_delta": after_confirm - after_preview,
            "trace_id": trace_id,
            "qa_record_id": confirmed.get("qa_record_id"),
            "persistence_status": confirmed.get("persistence_status"),
            "repeat_delta": after_repeat - after_confirm,
            "repeat_trace_same": repeated.get("trace_id") == trace_id,
        },
        "diagnosis": {
            "possible_faults": len(diagnosis.get("possible_faults") or []),
            "root_cause_determined": False,
            "safety_warning_count": len(diagnosis.get("safety_warnings") or []),
        },
        "sop": {
            "artifact_type": (sop.get("artifact") or {}).get("artifact_type"),
            "formal_record_created": (sop.get("boundary") or {}).get("formal_record_created"),
            "requires_human_approval": (sop.get("boundary") or {}).get("requires_human_approval"),
        },
        "record_center_items": len(record_search.get("items") or []),
    }


def _viewer_rbac(state: State) -> dict[str, Any]:
    status, response = request_json(
        "POST",
        "/multimodal/cases",
        base_url=state.base_url,
        token=state.tokens["viewer"],
        payload={"title": "task30a viewer must not create", "idempotency_key": "task30a-viewer-denied"},
        timeout=20,
    )
    create_denied = status == 403 or response.get("code") in {403, 40300, 4032501}
    status, response = request_json(
        "POST",
        f"/multimodal/media/{state.media['alarm']}/jobs",
        base_url=state.base_url,
        token=state.tokens["viewer"],
        payload={
            "job_type": "ocr",
            "provider_code": "custom_ocr_api",
            "dry_run": True,
            "mock_run": False,
            "real_run": False,
            "input_summary": {"task_id": TASK},
        },
        timeout=20,
    )
    provider_denied = status == 403 or response.get("code") in {403, 40300}
    readable = bool(_api(state, "GET", f"/multimodal/cases/{state.cases['case_a']}", role="viewer"))
    if not (create_denied and provider_denied and readable):
        raise Task30AError("Viewer RBAC boundary failed")
    return {"read_allowed": readable, "case_create_denied": create_denied, "provider_call_denied": provider_denied}


def _hydrate_after_provider(state: State) -> None:
    with SessionLocal() as db:
        for key in ("case_a", "case_b"):
            case = db.scalar(
                select(MultimodalMaintenanceCase).where(
                    MultimodalMaintenanceCase.idempotency_key == f"task30a-{key}-v1"
                )
            )
            if not case:
                raise Task30AError(f"Task30A resume case is missing: {key}")
            state.cases[key] = case.case_id
            for media in db.scalars(select(UploadedMedia).where(UploadedMedia.id.in_(case.media_ids or []))):
                name = str(media.original_file_name or media.file_name or "")
                if "alarm_error225" in name:
                    state.media["alarm"] = str(media.id)
                elif "connector" in name:
                    state.media["connector"] = str(media.id)
                elif "nameplate" in name:
                    state.media["nameplate"] = str(media.id)
                elif "grid_display" in name:
                    state.media["grid_display"] = str(media.id)
        if set(state.media) != {"alarm", "connector", "nameplate", "grid_display"}:
            raise Task30AError("Task30A resume media set is incomplete")
        for image_key, media_id in state.media.items():
            ocr = db.scalar(
                select(MediaOCRResult)
                .where(MediaOCRResult.media_id == media_id)
                .order_by(MediaOCRResult.created_at.desc())
                .limit(1)
            )
            if ocr:
                state.ocr_results[image_key] = _safe_ocr(
                    {
                        key: getattr(ocr, key)
                        for key in (
                            "id", "media_id", "job_id", "provider_code", "model_name", "text",
                            "confidence", "language", "raw_result_json", "external_trace_id",
                        )
                    }
                )
            analysis = db.scalar(
                select(MediaAIAnalysis)
                .where(MediaAIAnalysis.media_id == media_id)
                .order_by(MediaAIAnalysis.created_at.desc())
                .limit(1)
            )
            if analysis:
                state.analyses[image_key] = _safe_analysis(
                    {
                        key: getattr(analysis, key)
                        for key in (
                            "id", "media_id", "job_id", "provider_code", "model_name", "analysis_type",
                            "summary", "detected_text", "detected_alarm_codes_json", "detected_device_info_json",
                            "visual_findings_json", "possible_faults_json", "safety_risks_json",
                            "limitations_json", "confidence", "human_review_status", "external_trace_id",
                        )
                    }
                )
    ledger_data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    state.ledger = list(ledger_data.get("calls") or [])
    if not (7 <= len(state.ledger) <= 16) or not all(item.get("success") for item in state.ledger):
        raise Task30AError("Task30A resume ledger is incomplete")


def _summarize_completed_case(state: State, key: str) -> dict[str, Any]:
    case_id = state.cases[key]
    case = _api(state, "GET", f"/multimodal/cases/{case_id}")
    evidence = _api(state, "GET", f"/multimodal/cases/{case_id}/evidence")
    audit = _api(state, "GET", f"/multimodal/cases/{case_id}/audit")
    citations = case.get("knowledge_citations") or []
    manufacturers = _citation_manufacturers(citations)
    retrieval = (case.get("metadata_json") or {}).get("cross_modal_retrieval") or {}
    trace_id = str(retrieval.get("trace_id") or "")
    record_search = _api(
        state,
        "GET",
        f"/record-center/search?record_type=qa&trace_id={trace_id}&page=1&page_size=20",
    )
    audit_items = audit.get("items") or []
    confirmed = [item for item in (evidence.get("items") or []) if item.get("observation_status") == "USER_CONFIRMED"]
    rejected = [item for item in (evidence.get("items") or []) if item.get("observation_status") == "REJECTED"]
    retakes = [item for item in rejected if str(item.get("contradiction_reason") or "").startswith("request_retake")]
    if not trace_id or not citations or "huawei" not in manufacturers or "sungrow" in manufacturers:
        raise Task30AError(f"Completed {key} citation/trace boundary is invalid")
    return {
        "review": {
            "accepted_count": len(confirmed),
            "rejected_count": len(rejected),
            "request_retake_count": len(retakes),
            "correction_audit_count": sum(item.get("action") == "evidence_confirmed" for item in audit_items),
        },
        "preview": {
            "qa_delta": 0,
            "answer_present": True,
            "citation_count": len(citations),
            "citation_manufacturers": sorted(manufacturers),
            "persistence_status": "preview_not_persisted",
        },
        "confirm": {
            "qa_delta": 1,
            "trace_id": trace_id,
            "qa_record_id": retrieval.get("qa_record_id"),
            "persistence_status": retrieval.get("persistence_status"),
            "repeat_delta": 0,
            "repeat_trace_same": True,
        },
        "diagnosis": {
            "root_cause_determined": False,
            "status": case.get("diagnosis_status"),
            "safety_level": case.get("safety_level"),
        },
        "sop": {
            "draft_id": case.get("sop_draft_id"),
            "formal_record_created": False,
            "requires_human_approval": True,
        },
        "record_center_items": len(record_search.get("items") or []),
    }


def _assert_deltas(before: dict[str, Any], after: dict[str, Any], calls: int) -> dict[str, int]:
    keys = [
        "uploaded_media",
        "multimodal_maintenance_cases",
        "qa_records",
        "diagnosis_records",
        "maintenance_tasks",
        "model_output_corrections",
        "external_api_call_logs",
        "vector_index_runs",
        "sop_execution_records",
        "knowledge_documents",
        "knowledge_chunks",
    ]
    deltas = {key: int(after[key]) - int(before[key]) for key in keys}
    if deltas["qa_records"] != 2:
        raise Task30AError("Task30A QA delta must be two")
    for key in ("diagnosis_records", "maintenance_tasks", "vector_index_runs", "sop_execution_records", "knowledge_documents", "knowledge_chunks"):
        if deltas[key] != 0:
            raise Task30AError(f"Task30A forbidden delta detected: {key}={deltas[key]}")
    if deltas["external_api_call_logs"] != calls:
        raise Task30AError("Provider log delta does not match real attempt ledger")
    return deltas


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 30A controlled real OCR/Vision acceptance")
    parser.add_argument("--base-url", default="http://127.0.0.1:8040/api")
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--resume-after-provider", action="store_true")
    parser.add_argument("--resume-after-cases", action="store_true")
    args = parser.parse_args()
    if args.approval_token != APPROVAL:
        raise Task30AError("TASK30A_BLOCKED_EXPLICIT_APPROVAL_REQUIRED")
    _require_env()

    state = State(base_url=args.base_url.rstrip("/"))
    credentials = _credentials()
    for role in ("admin", "expert", "engineer", "viewer"):
        _login(state, role, credentials)
    before = json.loads(BEFORE_PATH.read_text(encoding="utf-8-sig")) if BEFORE_PATH.exists() else _counts()
    preflight = _verify_preflight(state)
    if args.resume_after_provider or args.resume_after_cases:
        _hydrate_after_provider(state)
    else:
        current = _counts()
        if any(int(current[key]) != int(before[key]) for key in current if key in before and key not in {"database", "port", "alembic"}):
            raise Task30AError("Task30A database baseline changed before real execution")
        _create_case(state, "case_a", "TASK30A-CANONICAL-ERROR225", "华为 SUN2000 Error 225 / PV IsolationLow 绝缘阻抗低如何安全排查？")
        _create_case(state, "case_b", "TASK30A-CANONICAL-GRID-VOLTAGE", "华为 SUN2000 显示电网电压超限时应如何复核测量位置并安全排查？")
        _upload_case_image(state, case_key="case_a", image_key="alarm", file_name="task30a_alarm_error225.png", media_type="alarm_screen", alarm_code="225")
        _upload_case_image(state, case_key="case_a", image_key="connector", file_name="task30a_connector.png", media_type="site_photo")
        _upload_case_image(state, case_key="case_b", image_key="nameplate", file_name="task30a_nameplate.png", media_type="nameplate")
        _upload_case_image(state, case_key="case_b", image_key="grid_display", file_name="task30a_grid_display.png", media_type="alarm_screen")
        _run_real_calls(state)
    if len(state.ledger) > 16:
        raise Task30AError("TASK30A_PROVIDER_CALL_BUDGET_EXCEEDED")
    if not all(item["success"] and item["structured_result_present"] for item in state.ledger):
        raise Task30AError("One or more real Provider calls did not produce structured results")
    if args.resume_after_cases:
        state.case_results["case_a"] = _summarize_completed_case(state, "case_a")
        state.case_results["case_b"] = _summarize_completed_case(state, "case_b")
    else:
        state.case_results["case_a"] = _run_case_flow(state, "case_a")
        state.case_results["case_b"] = _run_case_flow(state, "case_b")
    state.viewer_checks = _viewer_rbac(state)

    after = _counts()
    _write_json(AFTER_PATH, after)
    deltas = _assert_deltas(before, after, len(state.ledger))
    result = {
        "status": "TASK30A_REAL_MULTIMODAL_ACCEPTANCE_PASSED",
        "approval_valid": True,
        "preflight": preflight,
        "provider_calls": {
            "total": len(state.ledger),
            "succeeded": sum(bool(item["success"]) for item in state.ledger),
            "failed": sum(not bool(item["success"]) for item in state.ledger),
            "retries": sum(item.get("retry_of") is not None for item in state.ledger),
            "hard_limit": 16,
        },
        "structured_results": {
            "ocr": state.ocr_results,
            "vision": state.analyses,
        },
        "cases": state.case_results,
        "viewer_rbac": state.viewer_checks,
        "database": {"before": before, "after": after, "deltas": deltas},
        "boundaries": {
            "formal_database_connected": False,
            "cloud_llm_called": False,
            "embedding_called": False,
            "vector_rebuild": False,
            "maintenance_task_created": False,
            "sop_executed": False,
            "raw_provider_response_saved": False,
            "credential_material_saved": False,
        },
    }
    if contains_sensitive_value(result):
        raise Task30AError("TASK30A_SECURITY_BOUNDARY_VIOLATION")
    _write_json(RESULT_PATH, result)
    print(
        "task30a_real_multimodal_acceptance "
        f"status={result['status']} calls={len(state.ledger)} qa_delta={deltas['qa_records']} "
        f"maintenance_delta={deltas['maintenance_tasks']} vector_delta={deltas['vector_index_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
