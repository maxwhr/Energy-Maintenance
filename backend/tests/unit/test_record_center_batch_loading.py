from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from scripts.task25e_common import SQLTrace


def test_current_page_uses_fixed_batch_queries_without_n_plus_one() -> None:
    with SessionLocal() as db:
        with SQLTrace(db.get_bind()) as trace:
            result = RecordCenterService(db).search(page=1, page_size=100)
    assert result["items"]
    assert len(trace.statements) <= 40
    assert not any(item["category"].endswith("N_PLUS_ONE") for item in trace.statements)
