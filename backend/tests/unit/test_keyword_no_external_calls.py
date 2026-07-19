import inspect

from app.services.scoped_retrieval_engine import ScopedRetrievalEngine


def test_keyword_no_external_calls_contract():
    source = inspect.getsource(ScopedRetrievalEngine.retrieve)
    assert 'decision.actual_strategy != "keyword"' in source
    assert '"embedding": 0, "dashvector": 0' in source
