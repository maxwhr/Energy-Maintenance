from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
LOCAL_ENV = PROJECT_ROOT / ".env.task27a.test.local"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_local_database_url() -> None:
    if os.getenv("DATABASE_URL") or not LOCAL_ENV.exists():
        return
    for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()
            return


_load_local_database_url()

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import Device, KnowledgeDocument, QARecord, User  # noqa: E402
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest  # noqa: E402
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService  # noqa: E402
from app.services.record_center_service import RecordCenterService  # noqa: E402
from task28a_path_safety import assert_project_path  # noqa: E402


TEST_DATABASE = "energy_maintenance_task27a_test"
TEST_USERNAME = "task28a_qa_engineer"
TEST_DEVICE_CODE = "TASK28A-QA-DEVICE"
DEFAULT_REPORT = PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1" / "import_reports" / "qa_persistence_result.json"


def _atomic_report(path: Path, payload: dict) -> None:
    target = assert_project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def _assert_test_database() -> str:
    configured = str(engine.url.database or "")
    if configured != TEST_DATABASE:
        raise RuntimeError(f"refusing QA persistence writes outside {TEST_DATABASE}")
    with engine.connect() as connection:
        current = connection.scalar(text("SELECT current_database()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    if current != TEST_DATABASE:
        raise RuntimeError("connected database guard failed")
    if revision != "20260712_0015":
        raise RuntimeError(f"test database is not at expected Alembic head: {revision}")
    return current


def _fixture() -> tuple[UUID, UUID]:
    with SessionLocal() as db:
        approved_count = int(db.scalar(
            select(func.count()).select_from(KnowledgeDocument).where(
                KnowledgeDocument.manufacturer == "huawei",
                KnowledgeDocument.product_series == "SUN2000",
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.review_status == "approved",
                KnowledgeDocument.status == "active",
                KnowledgeDocument.metadata_json["task28a_corpus_id"].as_string() == "competition_corpus_v1",
            )
        ) or 0)
        if approved_count == 0:
            raise RuntimeError("Task 28A approved Huawei import is required before QA persistence acceptance")

        user = db.scalar(select(User).where(User.username == TEST_USERNAME))
        if user is None:
            user = User(
                username=TEST_USERNAME,
                display_name="Task 28A QA Engineer",
                role="engineer",
                status="active",
                is_active=True,
            )
            db.add(user)
            db.flush()
        device = db.scalar(select(Device).where(Device.device_code == TEST_DEVICE_CODE))
        if device is None:
            device = Device(
                device_code=TEST_DEVICE_CODE,
                device_name="Task 28A Isolated Test Inverter",
                manufacturer="huawei",
                product_series="SUN2000",
                model="SUN2000",
                device_type="pv_inverter",
                station_name="Task 28A Test Station",
                status="normal",
                metadata_json={"fixture_scope": "task28a_test_database_only"},
            )
            db.add(device)
            db.flush()
        db.commit()
        return user.id, device.id


def _query(user_id: UUID, device_id: UUID, request_id: str, *, persist_result: bool = True):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return QueryAwareRetrievalService(db, current_user=user).search(QueryAwareSearchRequest(
            query="华为 SUN2000 光伏逆变器绝缘阻抗低如何安全排查？",
            request_id=request_id,
            device_context={"device_id": str(device_id), "manufacturer": "huawei", "product_series": "SUN2000"},
            retrieval_mode="fast",
            top_k=5,
            enable_llm=False,
            allow_real_api=False,
            persist_result=persist_result,
        ))


def _rollback_probe(user_id: UUID, device_id: UUID, request_id: str) -> tuple[bool, str | None]:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        service = QueryAwareRetrievalService(db, current_user=user)

        def fail_after_flush(record: QARecord):
            db.add(record)
            db.flush()
            raise SQLAlchemyError("Task 28A injected rollback probe")

        service.qa_repository.create_qa_record = fail_after_flush  # type: ignore[method-assign]
        response = service.search(QueryAwareSearchRequest(
            query="华为 SUN2000 光伏逆变器绝缘阻抗低如何安全排查？",
            request_id=request_id,
            device_context={"device_id": str(device_id)},
            retrieval_mode="fast",
            enable_llm=False,
            allow_real_api=False,
            persist_result=True,
        ))
        remaining = int(db.scalar(select(func.count()).select_from(QARecord).where(QARecord.trace_id == response.trace_id)) or 0)
        session_usable = db.scalar(select(1)) == 1
        return response.persistence_status == "failed" and remaining == 0 and session_usable, response.trace_id


def main() -> int:
    report_path = DEFAULT_REPORT
    try:
        database_name = _assert_test_database()
        user_id, device_id = _fixture()
    except Exception as exc:  # noqa: BLE001 - emit a resumable blocked artifact.
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED",
            "database": engine.url.database,
            "reason": f"{type(exc).__name__}: {exc}",
            "writes_attempted": False,
            "checks": {
                "one_request_one_record": False,
                "same_request_id_idempotent": False,
                "concurrent_idempotent": False,
                "preview_zero_write": False,
                "rollback_verified": False,
                "trace_unique": False,
                "record_center_visible": False,
            },
        }
        _atomic_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    run_id = uuid4().hex[:16]
    first = _query(user_id, device_id, f"task28a-one-{run_id}")
    retry = _query(user_id, device_id, f"task28a-one-{run_id}")
    second = _query(user_id, device_id, f"task28a-two-{run_id}")

    with SessionLocal() as db:
        before_preview = int(db.scalar(select(func.count()).select_from(QARecord)) or 0)
    preview = _query(user_id, device_id, f"task28a-preview-{run_id}", persist_result=False)
    with SessionLocal() as db:
        after_preview = int(db.scalar(select(func.count()).select_from(QARecord)) or 0)

    concurrent_request = f"task28a-concurrent-{run_id}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent = list(executor.map(
            lambda _: _query(user_id, device_id, concurrent_request),
            range(2),
        ))
    rollback_ok, rollback_trace = _rollback_probe(user_id, device_id, f"task28a-rollback-{run_id}")

    with SessionLocal() as db:
        first_count = int(db.scalar(select(func.count()).select_from(QARecord).where(QARecord.trace_id == first.trace_id)) or 0)
        concurrent_count = int(db.scalar(select(func.count()).select_from(QARecord).where(
            QARecord.trace_id == concurrent[0].trace_id,
        )) or 0)
        record_center = RecordCenterService(db)
        list_result = record_center.search(record_type="qa", trace_id=first.trace_id, page=1, page_size=20)
        detail_result = record_center.detail(record_type="qa", record_id=UUID(str(first.qa_record_id)))
        trace_result = record_center.search(record_type="all", trace_id=first.trace_id, page=1, page_size=20)
        timeline_result = record_center.device_timeline(device_id=device_id, record_type="qa", limit=20)

    checks = {
        "one_request_one_record": first.persistence_status == "persisted" and first_count == 1,
        "same_request_id_idempotent": first.qa_record_id == retry.qa_record_id and first.trace_id == retry.trace_id and first_count == 1,
        "concurrent_idempotent": concurrent_count == 1 and len({item.qa_record_id for item in concurrent}) == 1,
        "preview_zero_write": preview.persistence_status == "skipped_preview" and before_preview == after_preview,
        "rollback_verified": rollback_ok,
        "trace_unique": first.trace_id != second.trace_id and bool(first.trace_id and second.trace_id),
        "record_center_visible": bool(
            list_result.get("items")
            and detail_result.get("record_id")
            and trace_result.get("items")
            and timeline_result.get("timeline")
        ),
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "database": database_name,
        "checks": checks,
        "trace_ids": {
            "one_request": first.trace_id,
            "second_request": second.trace_id,
            "concurrent": concurrent[0].trace_id,
            "preview": preview.trace_id,
            "rollback": rollback_trace,
        },
        "record_center": {
            "list": bool(list_result.get("items")),
            "detail": bool(detail_result.get("record_id")),
            "trace": bool(trace_result.get("items")),
            "timeline": bool(timeline_result.get("timeline")),
        },
        "external_provider_calls": 0,
    }
    _atomic_report(report_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
