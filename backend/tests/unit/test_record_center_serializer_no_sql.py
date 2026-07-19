from app.core.database import SessionLocal
from app.schemas.record_center import RecordCenterItem
from app.services.record_center_service import RecordCenterService
from scripts.task25e_common import SQLTrace


def test_serializer_does_not_issue_sql() -> None:
    with SessionLocal() as db:
        item = RecordCenterService(db).search(page=1, page_size=1)["items"][0]
        with SQLTrace(db.get_bind()) as trace:
            payload = RecordCenterItem.model_validate(item).model_dump()
    assert payload["record_id"]
    assert len(trace.statements) == 0

