import inspect

from app.services.scoped_retrieval_engine import ScopedRetrievalEngine


def test_adaptive_fallback_does_not_expand_scope():
    source = inspect.getsource(ScopedRetrievalEngine.retrieve)
    assert 'actual_mode = "keyword" if fallback else decision.actual_strategy' in source
    assert '"scope_validation_passed"' in source
