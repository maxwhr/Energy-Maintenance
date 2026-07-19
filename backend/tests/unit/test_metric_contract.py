from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from task25b_r3_dev_r2_common import rank_metrics


def test_single_relevant_contract_retains_raw_precision_but_uses_hit_metrics():
    metrics = rank_metrics(["target", "other"], {"target"})
    assert metrics["precision_at_5"] == 0.2
    assert metrics["hit_at_1"] == 1.0
    assert metrics["hit_at_5"] == 1.0
