from app.main import app


def test_official_pilot_paths_exist_but_are_separate_from_query_path():
    paths = app.openapi()["paths"]
    assert "/api/retrieval/benchmark/freeze" in paths
    assert "/api/retrieval/benchmark/run-official" in paths
    assert "/api/retrieval/query" in paths
