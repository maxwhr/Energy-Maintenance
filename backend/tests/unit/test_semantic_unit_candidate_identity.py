import inspect

from app.services.multi_query_retrieval_service import MultiQueryRetrievalService


def test_semantic_unit_maps_to_one_unit_candidate():
    source = inspect.getsource(MultiQueryRetrievalService._semantic)
    assert 'candidate.candidate_id = f"su:{unit.semantic_unit_id}"' in source
    assert "unit.source_chunks[:2]" not in source
