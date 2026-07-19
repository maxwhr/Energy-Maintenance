from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from task25b_r3_dev_r2_metrics import aggregate


def test_surfaced_precision_uses_actual_returned_count_not_fixed_five():
    row = {"surfaced_metrics": {"hit_at_1": 1, "hit_at_5": 1}, "raw_metrics": {"recall_at_5": 1, "recall_at_10": 1, "reciprocal_rank": 1, "ndcg_at_10": 1, "precision_at_5": .2, "r_precision": 1}, "surfaced_precision": 1, "surfaced_recall": 1, "irrelevant_result_rate": 0, "citation_valid": 1, "citation_coverage": 1, "scope_valid": True, "error": False, "latency_ms": 1, "is_no_answer": False, "surfaced_ids": ["x"], "is_model_case": False, "is_alarm_case": False, "relevance_cardinality": 1}
    assert aggregate([row])["surfaced_precision"] == 1.0
