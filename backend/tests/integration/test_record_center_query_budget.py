from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from scripts.task25e_common import SQLTrace


def test_overview_query_budget_is_below_hard_gate() -> None:
    with SessionLocal() as db:
        with SQLTrace(db.get_bind()) as trace:
            RecordCenterService(db).overview()
    assert len(trace.statements) <= 40
    assert len(trace.statements) <= 20
    assert not any(item["category"].endswith("N_PLUS_ONE") for item in trace.statements)

