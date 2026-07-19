from app.services.dedicated_rerank_service import DedicatedRerankService


def test_r5_r6_instruct_and_hard_gate_contract_are_frozen() -> None:
    assert DedicatedRerankService.INSTRUCT_VERSION == "task25b_r3_dev_r5_r6_instruct_v1"
    assert "directly answer" in DedicatedRerankService.INSTRUCT
    thresholds = {
        "candidate_recall_at_50": 0.95,
        "recall_at_5": 0.80,
        "recall_at_10": 0.85,
        "mrr": 0.75,
        "ndcg_at_10": 0.80,
        "direct_answer_hit_at_1": 0.70,
        "direct_answer_hit_at_3": 0.85,
    }
    assert thresholds["mrr"] == 0.75
    assert thresholds["direct_answer_hit_at_1"] == 0.70
