from app.services.vector_store_adapters import DashVectorAdapter


def test_dashvector_cosine_score_normalization_and_direction():
    values = [DashVectorAdapter.normalize_score(raw, metric="cosine") for raw in (0.0, 1.0, 2.0)]
    assert values == [1.0, 0.5, 0.0]
    assert values == sorted(values, reverse=True)


def test_dashvector_euclidean_distance_direction():
    assert DashVectorAdapter.normalize_score(0, metric="euclidean") > DashVectorAdapter.normalize_score(2, metric="euclidean")
