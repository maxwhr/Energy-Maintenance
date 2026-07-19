import inspect

from app.services.scoped_retrieval_engine import ScopedRetrievalEngine


def test_stage_latency_contains_required_retrieval_stages():
    source = inspect.getsource(ScopedRetrievalEngine.retrieve)
    for name in ("query_understanding_ms", "keyword_sql_ms", "keyword_scoring_ms", "embedding_ms",
                 "dashvector_ms", "postgres_validation_ms", "fusion_ms", "adaptive_route_ms",
                 "citation_validation_ms", "total_ms"):
        assert name in source
