from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from tests.record_center_test_support import item_ids


def test_pagination_has_stable_total_no_duplicates_or_omissions_in_sample() -> None:
    with SessionLocal() as db:
        pages = [RecordCenterService(db).search(page=page, page_size=25) for page in range(1, 5)]
    assert len({page["total"] for page in pages}) == 1
    flattened = [item for page in pages for item in item_ids(page["items"])]
    assert len(flattened) == len(set(flattened))
    assert len(flattened) == min(100, pages[0]["total"])

