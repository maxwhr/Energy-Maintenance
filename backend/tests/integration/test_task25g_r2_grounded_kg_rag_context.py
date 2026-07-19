import json

from task25g_r2_common import RUNTIME


def test_rag_integration_reports_truthful_blocker_and_safe_degradation():
    result = json.loads((RUNTIME / "kg_rag_integration.json").read_text(encoding="utf-8"))
    assert result["query_count"] == 20
    assert result["status"] == "BLOCKED_BY_CURRENT_EVIDENCE_GATE"
    assert result["kg_context_non_empty"] is False
    assert result["citation_metric_vacuous"] is True
    assert result["safe_degradation"] is True

