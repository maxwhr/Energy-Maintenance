from app.core.config import Settings


def test_pilot_collection_is_versioned_and_not_base_collection():
    settings = Settings(_env_file=None)
    assert settings.DASHVECTOR_PILOT_COLLECTION != settings.DASHVECTOR_PHYSICAL_COLLECTION
    assert "pilot" in settings.DASHVECTOR_PILOT_COLLECTION
    assert settings.TASK25B_ALLOW_FULL_REINDEX is False
