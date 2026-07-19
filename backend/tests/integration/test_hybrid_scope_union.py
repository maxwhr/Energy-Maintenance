import inspect

from app.services.scoped_retrieval_engine import ScopedRetrievalEngine


def test_hybrid_union_uses_only_scoped_keyword_and_vector_inputs():
    source = inspect.getsource(ScopedRetrievalEngine.retrieve)
    assert "scope=self.scope" in source
    assert "keyword_candidates=keyword_candidates, vector_hits=vector_hits" in source
