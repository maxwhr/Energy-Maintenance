import inspect

from app.services.multi_query_retrieval_service import MultiQueryRetrievalService


def test_raw_vector_trace_reports_raw_and_post_filter_hits():
    source = inspect.getsource(MultiQueryRetrievalService._raw_vector_with_trace)
    assert '"raw_hits"' in source and '"post_filter_hits"' in source
    assert "scope.partition_name" in source
