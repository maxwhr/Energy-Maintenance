import json

from task25g_r2_common import RUNTIME


def test_diagnosis_uses_scoped_graph_and_does_not_confirm_empty_context():
    result = json.loads((RUNTIME / "kg_diagnosis_grounding.json").read_text(encoding="utf-8"))
    assert result["diagnosis_calls_production_business_context"] is True
    assert result["diagnosis_context_non_empty"] is False
    assert result["automatic_diagnosis_confirmation"] is False
    assert result["workflow_graph_auto_writes"] == 0
    assert result["safe_degradation"] is True

