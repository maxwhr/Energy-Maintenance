import inspect

from app.services.scoped_retrieval_engine import ScopedRetrievalEngine


def test_adaptive_scope_is_preserved_by_engine_routes_and_fallback():
    source = inspect.getsource(ScopedRetrievalEngine.retrieve)
    assert "self.scope" in source
    assert 'actual_mode = "keyword" if fallback' in source
    assert '"effective_scope": self.scope.public_dict()' in source
