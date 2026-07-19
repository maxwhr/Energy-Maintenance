from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from task25b_r3_dev_r2_common import jaccard, kendall_like


def test_mode_distinctness_detects_different_rankings():
    assert jaccard(["a", "b"], ["c", "d"]) == 0
    assert kendall_like(["a", "b"], ["b", "a"]) == -1
