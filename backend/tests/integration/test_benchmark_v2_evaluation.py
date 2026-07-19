import inspect

from app.services.retrieval_evaluation_service import RetrievalEvaluationService


def test_benchmark_v2_uses_retrieval_only_scoped_engine():
    source = inspect.getsource(RetrievalEvaluationService._execute_case)
    assert "task25b_r3_dev_r1_zh_v2" in source
    assert "ScopedRetrievalEngine" in source
    assert "scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID" in source
