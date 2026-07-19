from sqlalchemy import func, insert, select

from app.core.database import SessionLocal
from app.models import KGExtractionRun
from app.services.record_center_service import RecordCenterService
from scripts.task25e_common import SQLTrace


MARKER = "task25e_pytest_large_transaction"


def test_query_count_does_not_grow_with_transactional_fixture() -> None:
    with SessionLocal() as db:
        with SQLTrace(db.get_bind()) as before:
            RecordCenterService(db).overview()
        nested = db.begin_nested()
        try:
            db.execute(insert(KGExtractionRun), [{"source_type": MARKER, "extractor": "pytest", "status": "pending", "metadata_json": {"fixture": True}} for _ in range(100)])
            db.flush()
            with SQLTrace(db.get_bind()) as after:
                RecordCenterService(db).overview()
            assert len(after.statements) <= 20
            assert len(after.statements) <= len(before.statements)
        finally:
            nested.rollback()
            db.rollback()
    with SessionLocal() as verify:
        assert int(verify.scalar(select(func.count()).select_from(KGExtractionRun).where(KGExtractionRun.source_type == MARKER)) or 0) == 0
