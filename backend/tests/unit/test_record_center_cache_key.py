from app.services.record_center_cache_service import RecordCenterCacheInvalidationService


def test_cache_key_contains_permission_and_query_identity() -> None:
    first = RecordCenterCacheInvalidationService.cache_key(user_id="u1", role="viewer", permission_fingerprint="viewer", filters={"status": "active"}, page=1, page_size=20, sort_direction="desc")
    second = RecordCenterCacheInvalidationService.cache_key(user_id="u2", role="viewer", permission_fingerprint="viewer", filters={"status": "active"}, page=1, page_size=20, sort_direction="desc")
    assert first != second
    assert first.startswith("record-center:")

