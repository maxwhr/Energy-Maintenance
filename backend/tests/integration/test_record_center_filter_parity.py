from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.repositories.record_center_query_repository import RECORD_TYPE_ORDER
from app.repositories.record_center_repository import RecordCenterRepository
from app.services.record_center_service import RecordCenterService


def test_manufacturer_filter_matches_legacy_semantics() -> None:
    with SessionLocal() as db:
        legacy_repository = RecordCenterRepository(db)
        legacy = []
        for record_type in RECORD_TYPE_ORDER:
            legacy.extend(legacy_repository._items_for_type(record_type, device_id=None, keyword=None, trace_id=None, status=None, fault_type=None, alarm_code=None, manufacturer="huawei", product_series=None, date_from=None, date_to=None))
        legacy.sort(key=lambda item: item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        current = RecordCenterService(db).search(manufacturer="huawei", page=1, page_size=100)
    assert current["total"] == len(legacy)
    assert [str(item["record_id"]) for item in current["items"]] == [str(item["record_id"]) for item in legacy[:100]]

