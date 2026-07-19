from types import SimpleNamespace

from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from tests.minimax_test_helpers import candidate, understanding


def test_explicit_wrong_model_is_removed_before_provider() -> None:
    u = understanding("SUN2000-100KTL 通信异常如何处理")
    u.device_models = ["SUN2000-100KTL"]
    wrong = candidate("wrong", content="LUNA2000-200KWH 通信处理", rrf=0.8)
    wrong.chunk = SimpleNamespace(metadata_json={"device_models": ["LUNA2000-200KWH"]})
    right = candidate("right", content="SUN2000-100KTL 通信处理", rrf=0.2, exact_model=True)
    right.chunk = SimpleNamespace(metadata_json={"device_models": ["SUN2000-100KTL"]})
    result = PreRerankHardGuardService().apply([wrong, right], understanding=u)
    assert [item.candidate_id for item in result.candidates] == ["right"]
    assert result.diagnostics["removals"][0]["reason"] == "EXPLICIT_WRONG_MODEL"
