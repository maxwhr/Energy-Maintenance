from app.services.record_center_cache_service import RecordCenterCacheInvalidationService


def test_role_and_permission_fingerprint_cannot_share_cache_identity() -> None:
    common = dict(user_id="same", filters={}, page=1, page_size=20, sort_direction="desc")
    viewer = RecordCenterCacheInvalidationService.cache_key(role="viewer", permission_fingerprint="read", **common)
    admin = RecordCenterCacheInvalidationService.cache_key(role="admin", permission_fingerprint="admin", **common)
    assert viewer != admin

