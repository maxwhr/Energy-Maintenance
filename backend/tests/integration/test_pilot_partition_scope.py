import inspect

from app.services.vector_index_service import VectorIndexService


def test_pilot_partition_must_match_scope():
    source = inspect.getsource(VectorIndexService.search)
    assert "retrieval_scope_collection_or_partition_mismatch" in source
    assert 'config["namespace"] != scope.partition_name' in source
