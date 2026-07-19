import pytest

from app.services.record_center_service import RecordCenterService, RecordCenterServiceError


@pytest.mark.parametrize("page,page_size", [(0, 20), (1, 0), (1, 101)])
def test_pagination_bounds_are_enforced(page: int, page_size: int) -> None:
    with pytest.raises(RecordCenterServiceError):
        RecordCenterService._validate_page(page, page_size)

