from types import SimpleNamespace
from uuid import uuid4

from app.services.vector_index_service import VectorIndexService


def test_vector_id_changes_with_collection_scope_for_reversible_lifecycle():
    chunk_id = uuid4()
    base = VectorIndexService._vector_id(chunk_id, {"collection_name": "base", "namespace": "default"})
    pilot = VectorIndexService._vector_id(chunk_id, {"collection_name": "pilot", "namespace": "default"})
    assert base != pilot
    assert base == VectorIndexService._vector_id(chunk_id, {"collection_name": "base", "namespace": "default"})
