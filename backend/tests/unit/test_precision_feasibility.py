from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from task25b_r3_dev_r2_common import rank_metrics


def test_fewer_than_three_relevant_items_cannot_reach_point_forty_five_at_five():
    assert rank_metrics(["a", "b"], {"a"})["precision_at_5"] == 0.2
    assert rank_metrics(["a", "b"], {"a", "b"})["precision_at_5"] == 0.4
