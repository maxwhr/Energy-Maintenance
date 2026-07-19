from app.core.database import SessionLocal
from app.repositories.record_center_query_repository import RecordCenterQueryRepository
from scripts.task25e_common import SQLTrace


def test_overview_counts_are_one_fixed_aggregate_query() -> None:
    with SessionLocal() as db:
        repository = RecordCenterQueryRepository(db)
        with SQLTrace(db.get_bind()) as trace:
            counts = repository.aggregate_overview_counts()
    assert len(trace.statements) == 1
    assert counts["qa_records"] >= 0
    assert counts["devices"] >= 0
    assert len(counts) == 12

