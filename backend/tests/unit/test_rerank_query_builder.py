from app.services.rerank_query_builder import RerankQueryBuilder
from tests.minimax_test_helpers import understanding


def test_query_builder_uses_only_query_understanding_contract() -> None:
    built = RerankQueryBuilder().build(understanding("SUN2000 告警2031发生后如何处理"))
    assert "原始查询" in built.text
    assert "规范查询" in built.text
    assert "请求信息" in built.text
    assert "expected" not in built.text.lower()
    assert "candidate_id" not in built.text.lower()
    assert len(built.text_hash) == 64
