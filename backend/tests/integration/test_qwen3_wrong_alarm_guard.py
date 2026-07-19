from types import SimpleNamespace

from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from tests.minimax_test_helpers import candidate, understanding


def test_explicit_wrong_alarm_is_removed_before_provider() -> None:
    u = understanding("告警2031如何处理")
    u.alarm_codes = ["2031"]
    wrong = candidate("wrong", content="告警2064的处理", rrf=0.8)
    wrong.chunk = SimpleNamespace(metadata_json={"alarm_codes": ["2064"]})
    right = candidate("right", content="告警2031的处理", rrf=0.2, exact_alarm=True)
    right.chunk = SimpleNamespace(metadata_json={"alarm_codes": ["2031"]})
    result = PreRerankHardGuardService().apply([wrong, right], understanding=u)
    assert [item.candidate_id for item in result.candidates] == ["right"]
    assert result.diagnostics["removals"][0]["reason"] == "EXPLICIT_WRONG_ALARM"
