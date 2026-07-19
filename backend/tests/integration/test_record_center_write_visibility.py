from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import KGExtractionRun
from app.services.record_center_service import RecordCenterService


MARKER = "task25e_pytest_write_visibility"


def test_flushed_write_is_visible_and_transaction_is_rolled_back() -> None:
    with SessionLocal() as db:
        nested = db.begin_nested()
        try:
            row = KGExtractionRun(source_type=MARKER, extractor="pytest", status="pending", metadata_json={"fixture": True})
            db.add(row)
            db.flush()
            result = RecordCenterService(db).search(record_type="knowledge_graph_extraction_run", keyword=MARKER)
            assert any(item["record_id"] == row.id for item in result["items"])
        finally:
            nested.rollback()
            db.rollback()
    with SessionLocal() as verify:
        assert int(verify.scalar(select(func.count()).select_from(KGExtractionRun).where(KGExtractionRun.source_type == MARKER)) or 0) == 0

