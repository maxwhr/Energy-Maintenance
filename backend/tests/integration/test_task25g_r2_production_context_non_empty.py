import json

from task25g_r2_common import RUNTIME


def test_empty_production_context_is_not_reported_as_non_vacuous_pass():
    result = json.loads((RUNTIME / "non_vacuous_context.json").read_text(encoding="utf-8"))
    assert result["empty_context"] is True
    assert result["vacuous_metric"] is True
    assert result["current_valid_evidence_coverage"] == 0.0
    assert result["status"] == "TASK25G_R2_NON_VACUOUS_GROUNDING_GATE_FAILED"

