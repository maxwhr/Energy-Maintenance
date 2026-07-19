from app.services.rag_raw_channel_snapshot import (
    RawRetrievalCandidateSnapshot,
    RawRetrievalChannelSnapshot,
    snapshot_from_dict,
)


def snapshot():
    return RawRetrievalChannelSnapshot.create(
        case_id="case-1", query_hash="q" * 64, scope_fingerprint="s" * 64,
        planner_version="planner-v1", retrieval_config_version="config-v1",
        channel="RAW_VECTOR", variant_id="v1", variant_type="ORIGINAL", variant_hash="v" * 64,
        collection="collection", partition="partition", top_k=10, filter_hash="f" * 64,
        vector_hash="x" * 64, response_status="SUCCESS", provider_request_hash="r" * 64,
        candidates=(RawRetrievalCandidateSnapshot(
            provider_candidate_id="p1", evidence_source_type="CHUNK", score=0.9, rank=1,
            metadata_hash="m" * 64, document_id="d1", chunk_id="c1", source_chunk_ids=("c1",),
        ),),
    )


def test_raw_channel_snapshot_round_trip_keeps_only_safe_fields():
    value = snapshot()
    restored = snapshot_from_dict(value.public_dict())
    assert restored.verify()
    assert restored.candidates[0].provider_candidate_id == "p1"
    serialized = value.public_dict()
    assert "vector" not in serialized
    assert "query" not in serialized
    assert "content" not in serialized["candidates"][0]
