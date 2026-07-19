from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from tests.record_center_test_support import item_ids


def test_stable_sort_has_no_cross_page_duplicates() -> None:
    with SessionLocal() as db:
        service = RecordCenterService(db)
        first = service.search(page=1, page_size=30)
        second = service.search(page=2, page_size=30)
        repeat = service.search(page=1, page_size=30)
    assert item_ids(first["items"]) == item_ids(repeat["items"])
    assert set(item_ids(first["items"])).isdisjoint(item_ids(second["items"]))

