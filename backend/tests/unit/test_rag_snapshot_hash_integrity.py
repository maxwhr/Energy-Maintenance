from app.services.rag_raw_channel_snapshot import snapshot_from_dict
from tests.unit.test_rag_raw_channel_snapshot import snapshot


def test_snapshot_hash_rejects_candidate_mutation():
    value = snapshot().public_dict()
    value["candidates"][0]["score"] = 0.1
    assert not snapshot_from_dict(value).verify()
