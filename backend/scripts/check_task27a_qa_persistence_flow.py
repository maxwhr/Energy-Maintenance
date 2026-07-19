from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, QARecord, User  # noqa: E402
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest  # noqa: E402
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService  # noqa: E402
from app.services.record_center_service import RecordCenterService  # noqa: E402


TEST_USERNAME = "task27a_rag_test_engineer"
TEST_DOCUMENT_TITLE = "Task27A isolated Huawei SUN2000 maintenance evidence"


def assert_test_database_name(database_name: str | None) -> str:
    normalized = str(database_name or "").casefold()
    if "_test" not in normalized and "task27a" not in normalized:
        raise RuntimeError("refusing QA persistence test: database name must contain _test or task27a")
    return str(database_name)


def _seed_minimum_fixture() -> tuple[UUID, UUID]:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == TEST_USERNAME))
        if user is None:
            user = User(
                username=TEST_USERNAME,
                display_name="Task 27A Test Engineer",
                role="engineer",
                status="active",
                is_active=True,
            )
            db.add(user)
            db.flush()
        document = db.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.title == TEST_DOCUMENT_TITLE,
        ))
        if document is None:
            document = KnowledgeDocument(
                title=TEST_DOCUMENT_TITLE,
                manufacturer="huawei",
                product_series="SUN2000",
                model="SUN2000-100KTL-M1",
                device_type="pv_inverter",
                document_type="manual",
                source="task27a_isolated_test_source",
                source_type="vendor_official",
                parse_status="parsed",
                chunk_count=1,
                review_status="approved",
                status="active",
                metadata_json={
                    "normalized_language": "zh-CN",
                    "is_current_version": True,
                },
            )
            db.add(document)
            db.flush()
            db.add(KnowledgeChunk(
                document_id=document.id,
                manufacturer="huawei",
                product_series="SUN2000",
                device_type="pv_inverter",
                document_type="manual",
                chunk_index=0,
                content=(
                    "SUN2000 绝缘阻抗低时，应先执行停机、断开交直流电源并验电。"
                    "检查直流组串、电缆和连接器是否存在对地绝缘异常或受潮，排除异常后复检并记录。"
                ),
                section_title="绝缘阻抗低排查",
                char_count=78,
                page_number=1,
                embedding_status="pending",
                metadata_json={"source_locator": {"page_number": 1, "section_title": "绝缘阻抗低排查"}},
                status="active",
            ))
        db.commit()
        return user.id, document.id


def _query(user_id: UUID, request_id: str, *, persist_result: bool = True):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return QueryAwareRetrievalService(db, current_user=user).search(QueryAwareSearchRequest(
            query="华为 SUN2000-100KTL-M1 绝缘阻抗低如何排查",
            request_id=request_id,
            retrieval_mode="fast",
            enable_llm=False,
            allow_real_api=False,
            persist_result=persist_result,
        ))


def main() -> int:
    try:
        database_name = assert_test_database_name(engine.url.database)
    except RuntimeError as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "database_name": engine.url.database,
            "reason": str(exc),
            "writes_attempted": False,
        }, ensure_ascii=False, indent=2))
        return 2
    user_id, document_id = _seed_minimum_fixture()
    first = _query(user_id, "task27a-idempotent-request")
    retry = _query(user_id, "task27a-idempotent-request")
    second = _query(user_id, "task27a-second-request")
    preview = _query(user_id, "task27a-preview-request", persist_result=False)
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent = list(executor.map(
            lambda _: _query(user_id, "task27a-concurrent-request"),
            range(2),
        ))

    with SessionLocal() as db:
        idempotent_count = int(db.scalar(select(func.count()).select_from(QARecord).where(
            QARecord.trace_id == first.trace_id,
        )) or 0)
        preview_count = int(db.scalar(select(func.count()).select_from(QARecord).where(
            QARecord.trace_id == preview.trace_id,
        )) or 0)
        concurrent_count = int(db.scalar(select(func.count()).select_from(QARecord).where(
            QARecord.trace_id == concurrent[0].trace_id,
        )) or 0)
        record_page = RecordCenterService(db).search(
            record_type="qa",
            trace_id=first.trace_id,
            page=1,
            page_size=20,
        )
        record_center_visible = bool(record_page.get("items"))

    checks = {
        "database_guard_passed": True,
        "answer_returned": bool(first.answer),
        "references_returned": bool(first.references),
        "trace_returned": bool(first.trace_id),
        "one_request_one_record": idempotent_count == 1,
        "same_request_id_idempotent": first.qa_record_id == retry.qa_record_id and idempotent_count == 1,
        "new_request_creates_new_record": first.qa_record_id != second.qa_record_id,
        "persist_false_zero_write": preview.persistence_status == "skipped_preview" and preview_count == 0,
        "concurrent_duplicate_safe": concurrent_count == 1 and len({item.qa_record_id for item in concurrent}) == 1,
        "record_center_visible": record_center_visible,
        "no_external_provider_call": all(item.provider_status.get("generation") == "rule_based" for item in (first, retry, second)),
    }
    result = {
        "database_name": database_name,
        "fixture_document_id": str(document_id),
        "checks": checks,
        "passed": all(checks.values()),
        "trace_ids": {
            "idempotent": first.trace_id,
            "second": second.trace_id,
            "preview": preview.trace_id,
            "concurrent": concurrent[0].trace_id,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
