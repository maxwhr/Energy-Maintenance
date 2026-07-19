from sqlalchemy import union_all

from app.core.database import SessionLocal
from app.repositories.record_center_query_repository import RECORD_TYPE_ORDER, RecordCenterQueryRepository


def test_query_plan_is_a_database_union_with_bounded_page() -> None:
    empty = {key: None for key in ("device_id", "workflow_id", "actor_id", "keyword", "trace_id", "status", "fault_type", "alarm_code", "manufacturer", "product_series", "date_from", "date_to")}
    with SessionLocal() as db:
        repository = RecordCenterQueryRepository(db)
        statement = union_all(*(repository._identity_select(record_type, empty) for record_type in RECORD_TYPE_ORDER))
        sql = str(statement.compile(dialect=db.get_bind().dialect))
    assert sql.count("UNION ALL") == len(RECORD_TYPE_ORDER) - 1
    assert "record_center" not in sql.lower() or "identity" in sql.lower()

