from app.services.task25g_r2_grounding_service import Task25GR2GroundingService


def _item(index: int, kind: str, relation: str | None, category: str) -> dict:
    return {
        "fact_id": f"{kind.lower()}:{index}",
        "fact_kind": kind,
        "fact_category": category,
        "relation_type": relation,
        "candidate_id": f"candidate-{index}",
        "support_level": "DIRECT_EXACT_SUPPORT",
    }


def test_non_vacuous_gate_rejects_node_heavy_ten_fact_core():
    values = [_item(index, "NODE", None, "IDENTITY_FACT") for index in range(9)]
    values.append(_item(9, "EDGE", "HAS_SYMPTOM", "DIAGNOSTIC_FACT"))
    gate = Task25GR2GroundingService.evaluate_gate(values)
    assert not gate["passed"]
    assert not gate["checks"]["grounded_edges_at_least_5"]
    assert not gate["checks"]["relation_types_at_least_2"]

