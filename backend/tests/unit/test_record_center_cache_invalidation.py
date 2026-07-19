from app.services.record_center_cache_service import RecordCenterCacheInvalidationService


def test_invalidation_changes_data_version_and_cache_key() -> None:
    arguments = dict(user_id="u1", role="admin", permission_fingerprint="admin", filters={}, page=1, page_size=20, sort_direction="desc")
    before = RecordCenterCacheInvalidationService.cache_key(**arguments)
    old_version = RecordCenterCacheInvalidationService.current_version()
    assert RecordCenterCacheInvalidationService.invalidate("unit_test") == old_version + 1
    assert RecordCenterCacheInvalidationService.cache_key(**arguments) != before

