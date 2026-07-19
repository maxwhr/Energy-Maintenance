from types import SimpleNamespace

from app.services.rerank_document_builder import RerankDocumentBuilder
from tests.minimax_test_helpers import candidate, understanding


def test_document_builder_is_source_grounded_bounded_and_hashed() -> None:
    item = candidate("direct", content=("告警2031原因是组串绝缘异常，应断电检查并验证告警消失。" * 80), rrf=0.2)
    item.chunk = SimpleNamespace(metadata_json={"device_models": ["SUN2000-100KTL"], "alarm_codes": ["2031"]})
    item.document = SimpleNamespace(metadata_json={"document_type": "alarm_code", "product_family": "SUN2000"})
    built = RerankDocumentBuilder().build(item, understanding=understanding("SUN2000 告警2031原因和处理"))
    assert "设备型号：SUN2000-100KTL" in built.text
    assert "来源摘录：" in built.text
    assert 800 <= built.text_length <= 1500
    assert len(built.text_hash) == 64
    assert "expected_id" not in built.text.lower()
