from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


def test_cosine_distance_direction_and_anchor_order():
    self_match = DashVectorAdapter.normalize_score(0.0, metric="cosine")
    high = DashVectorAdapter.normalize_score(0.2, metric="cosine")
    unrelated = DashVectorAdapter.normalize_score(1.8, metric="cosine")
    assert self_match == 1.0
    assert self_match > high > unrelated

