from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from task25b_r3_dev_r2_metrics import applicability


def test_no_model_case_is_not_reported_as_zero_or_one_accuracy():
    metric = applicability([{"is_model_case": False}], "model")
    assert metric["applicable"] is False
    assert metric["query_extraction"] is None
