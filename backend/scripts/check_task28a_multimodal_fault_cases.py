from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select, text
from starlette.datastructures import Headers


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
CORPUS_ROOT = PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1"
LOCAL_ENV = PROJECT_ROOT / ".env.task27a.test.local"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_local_database_url() -> None:
    if os.getenv("DATABASE_URL") or not LOCAL_ENV.exists():
        return
    for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()
            break


_load_local_database_url()
ALLOW_REAL_PROVIDER = os.getenv("TASK28A_ALLOW_REAL_PROVIDER", "").strip().casefold() == "true"
os.environ["UPLOAD_DIR"] = "storage/tmp/task28a_test_uploads"
if not ALLOW_REAL_PROVIDER:
    for key in ("OCR_ENABLED", "MIMO_ENABLED", "CLOUD_VISION_ENABLED", "CLOUD_LLM_ENABLED", "LOCAL_LLM_ENABLED"):
        os.environ[key] = "false"

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import KnowledgeDocument, User  # noqa: E402
from app.schemas.multimodal_case import (  # noqa: E402
    EvidenceDecisionRequest,
    MultimodalAnalyzeRequest,
    MultimodalCaseCreate,
    MultimodalDiagnoseRequest,
    MultimodalEvidenceCreate,
    MultimodalRetrieveRequest,
    MultimodalSopDraftRequest,
)
from app.services.media_service import MediaService  # noqa: E402
from app.services.multimodal_case_orchestrator_service import MultimodalCaseOrchestratorService  # noqa: E402
from app.services.multimodal_case_state_service import MultimodalCaseStateService  # noqa: E402
from app.services.record_center_service import RecordCenterService  # noqa: E402


TEST_DATABASE = "energy_maintenance_task27a_test"
EXPECTED_REVISION = "20260712_0015"
DEFAULT_REPORT = CORPUS_ROOT / "import_reports" / "multimodal_fault_case_result.json"
ANNOTATIONS = (
    CORPUS_ROOT / "annotations" / "fault_case_01.json",
    CORPUS_ROOT / "annotations" / "fault_case_02.json",
)
PROHIBITED_CASE_01_CLAIMS = (
    "一定是某个组件损坏",
    "一定是 MC4",
    "带电逐路拆接",
    "绕过绝缘检测",
    "手动重启就是解决方案",
)


def _atomic_report(payload: dict) -> None:
    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = DEFAULT_REPORT.with_name(f".{DEFAULT_REPORT.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, DEFAULT_REPORT)


def _assert_test_database() -> None:
    if engine.url.database != TEST_DATABASE:
        raise RuntimeError(f"refusing multimodal writes outside {TEST_DATABASE}")
    with engine.connect() as connection:
        current = connection.scalar(text("SELECT current_database()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    if current != TEST_DATABASE:
        raise RuntimeError("connected database guard failed")
    if revision != EXPECTED_REVISION:
        raise RuntimeError(f"unexpected Alembic revision: {revision}")


def _test_user() -> UUID:
    with SessionLocal() as db:
        imported = int(db.scalar(
            select(func.count()).select_from(KnowledgeDocument).where(
                KnowledgeDocument.manufacturer == "huawei",
                KnowledgeDocument.product_series == "SUN2000",
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.review_status == "approved",
                KnowledgeDocument.status == "active",
                KnowledgeDocument.metadata_json["task28a_corpus_id"].as_string() == "competition_corpus_v1",
            )
        ) or 0)
        if imported == 0:
            raise RuntimeError("approved Task 28A Huawei documents are required before multimodal acceptance")
        user = db.scalar(
            select(User)
            .where(User.role.in_(("admin", "expert", "engineer")), User.is_active.is_(True), User.status == "active")
            .order_by(User.created_at.asc())
        )
        if not user:
            raise RuntimeError("an active editor user is required")
        return user.id


def _annotation_query(annotation: dict) -> str:
    note = annotation.get("user_supplied_case_note") or {}
    note_text = "；".join(str(value) for value in note.values() if value and not isinstance(value, list))
    return (
        f"{annotation['title']}。{note_text}。"
        "请在当前 Huawei SUN2000 官方知识范围内检索可参考的排查方向；现场设备厂家和型号仍待人员确认。"
    )[:3900]


def _manual_observation(annotation: dict) -> tuple[str, str, list[str]]:
    if annotation["case_id"] == "FAULT_CASE_01_PV_ISOLATION_LOW":
        return "ALARM_CODE", "Error: 225 / PV IsolationLow / PV 绝缘阻抗低", ["225"]
    return "ALARM_NAME", "电网电压超限", []


async def _run_case(annotation_path: Path, user_id: UUID) -> dict:
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    image_path = Path(annotation["image_project_path"])
    if hashlib.sha256(image_path.read_bytes()).hexdigest() != annotation["image_sha256"]:
        raise RuntimeError(f"image hash mismatch: {annotation['case_id']}")

    with SessionLocal() as db:
        user = db.get(User, user_id)
        state = MultimodalCaseStateService(db)
        created = state.create(MultimodalCaseCreate(
            title=annotation["title"],
            user_query=_annotation_query(annotation),
            product_family=None,
            equipment_category="pv_inverter",
            reported_symptoms=[annotation["title"]],
            occurrence_conditions=[
                str(value)
                for value in (annotation.get("structured_expectation") or {}).values()
                if isinstance(value, str)
            ][:10],
            idempotency_key=f"task28a-r2c-{annotation['case_id'].casefold()}",
        ), user)
        case = state.get(created.case_id, user)
        media_service = MediaService(db)
        media_type = "alarm_screen"
        with image_path.open("rb") as handle:
            uploaded = await media_service.upload_media(
                file=UploadFile(
                    file=handle,
                    filename=image_path.name,
                    headers=Headers({"content-type": mimetypes.guess_type(image_path.name)[0] or "image/jpeg"}),
                ),
                media_type=media_type,
                description="Task 28A user-supplied fault image; pending expert review.",
                manufacturer=None,
                product_series=None,
                device_type="unknown",
                device_id=None,
                task_id=None,
                fault_type=annotation.get("fault_type"),
                alarm_code=annotation.get("possible_alarm_code"),
                current_user=user,
            )
        orchestrator = MultimodalCaseOrchestratorService(db)
        orchestrator.attach_media(case, uploaded["media"], user)
        case = state.get(case.case_id, user)

        evidence_type, confirmed_text, alarm_codes = _manual_observation(annotation)
        observation_hash = hashlib.sha256(
            f"{annotation['image_sha256']}:{confirmed_text}:manual-visual-confirmation".encode("utf-8")
        ).hexdigest()
        evidence = state.add_evidence(case, MultimodalEvidenceCreate(
            media_id=uploaded["media"].id,
            modality="IMAGE",
            evidence_type=evidence_type,
            source_type="USER_INPUT",
            source_hash=observation_hash,
            observed_text=confirmed_text,
            normalized_text=confirmed_text,
            alarm_code_candidates=alarm_codes,
            symptom_candidates=[annotation["title"]],
            confidence=1.0,
            observation_status="OBSERVED",
            metadata_json={
                "manual_visual_confirmation_required": True,
                "not_an_ocr_result": True,
                "annotation_case_id": annotation["case_id"],
            },
        ), user)
        confirmed = state.decide_evidence(
            case,
            evidence.evidence_id,
            EvidenceDecisionRequest(
                reason="Task 28A audited manual confirmation; provider output was not substituted.",
                confirmed_value=confirmed_text,
            ),
            user,
            accept=True,
        )
        case = state.get(case.case_id, user)
        analysis = orchestrator.analyze(case, MultimodalAnalyzeRequest(
            dry_run=not ALLOW_REAL_PROVIDER,
            mock_run=False,
            allow_real_api=ALLOW_REAL_PROVIDER,
            force=False,
        ), user)
        case = state.get(case.case_id, user)
        retrieval = orchestrator.retrieve(case, MultimodalRetrieveRequest(
            top_k=5,
            requested_information=["possible_causes", "inspection_steps", "safety_notes"],
        ), user)
        case = state.get(case.case_id, user)
        diagnosis = None
        sop = None
        if retrieval.get("citations") and case.status in {"EVIDENCE_READY", "DIAGNOSIS_READY", "MULTIPLE_POSSIBILITIES"}:
            diagnosis = orchestrator.diagnose(case, MultimodalDiagnoseRequest(proposed_actions=[]), user)
            case = state.get(case.case_id, user)
            sop = orchestrator.create_sop_draft(
                case,
                MultimodalSopDraftRequest(title=f"{annotation['title']} 检修 SOP 草稿"),
                user,
            )

        trace_id = retrieval.get("trace_id")
        record_visible = False
        record_detail_visible = False
        if trace_id:
            center = RecordCenterService(db)
            page = center.search(record_type="qa", trace_id=trace_id, page=1, page_size=20)
            record_visible = bool(page.get("items"))
            if page.get("items"):
                detail = center.detail(record_type="qa", record_id=UUID(str(page["items"][0]["record_id"])))
                record_detail_visible = bool(detail.get("record_id"))
        audit = orchestrator.audit(case)
        answer = retrieval.get("answer") or ""
        unsafe_claims = [claim for claim in PROHIBITED_CASE_01_CLAIMS if claim in answer]
        ocr_status = uploaded["ocr"].status
        ocr_actual = uploaded["ocr"].text if ocr_status == "processed" else ""
        return {
            "annotation_case_id": annotation["case_id"],
            "multimodal_case_id": case.case_id,
            "media_id": str(uploaded["media"].id),
            "media_uploaded": True,
            "media_deduplicated": bool(uploaded.get("deduplicated")),
            "ocr_status": ocr_status,
            "ocr_actual_text": ocr_actual,
            "vision_status": "CALLED" if analysis.get("external_api_called") else "BLOCKED_NOT_CALLED",
            "manual_confirmation": bool(confirmed.user_confirmed),
            "confirmed_text": confirmed.normalized_text,
            "retrieval_query": [item.get("query") for item in retrieval.get("generated_queries", [])],
            "answer": answer,
            "references": retrieval.get("references") or [],
            "citations": retrieval.get("citations") or [],
            "trace_id": trace_id,
            "qa_record_id": retrieval.get("qa_record_id"),
            "qa_persistence_status": retrieval.get("persistence_status"),
            "diagnosis_created": diagnosis is not None,
            "diagnosis": diagnosis,
            "sop_boundary": (sop or {}).get("boundary"),
            "record_center_visible": record_visible,
            "record_center_detail_visible": record_detail_visible,
            "audit_events": len(audit),
            "unsafe_claims": unsafe_claims,
            "external_provider_called": bool(analysis.get("external_api_called")),
            "passed": bool(
                confirmed.user_confirmed
                and retrieval.get("citations")
                and trace_id
                and retrieval.get("qa_record_id")
                and record_visible
                and record_detail_visible
                and not unsafe_claims
            ),
        }


def main() -> int:
    try:
        _assert_test_database()
        user_id = _test_user()
    except Exception as exc:  # noqa: BLE001 - preserve the exact blocker without writing test data.
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED",
            "database": engine.url.database,
            "reason": f"{type(exc).__name__}: {exc}",
            "provider_opt_in": ALLOW_REAL_PROVIDER,
            "external_provider_calls": 0,
            "writes_attempted": False,
            "cases": [],
        }
        _atomic_report(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    results = [asyncio.run(_run_case(path, user_id)) for path in ANNOTATIONS]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if all(item["passed"] for item in results) else "FAILED",
        "database": TEST_DATABASE,
        "provider_opt_in": ALLOW_REAL_PROVIDER,
        "external_provider_calls": sum(item["external_provider_called"] for item in results),
        "cases": results,
    }
    _atomic_report(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
