from app.services.query_understanding_contract_gate import QueryUnderstandingContractGate


def test_canary_contract_blocks_when_no_model_meets_runtime_gate() -> None:
    result = QueryUnderstandingContractGate.evaluate(
        model_ab={"selected_runtime_model": "deterministic", "models": {}},
        context_merge={"accuracy": 1.0},
        planner_probe={"status": "PASSED"},
        deterministic_rerank={"status": "PASSED"},
    )
    assert result["ready"] is False
    assert result["status"] == "QUERY_UNDERSTANDING_CONTRACT_NOT_READY"
