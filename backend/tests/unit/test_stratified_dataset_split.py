from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from task25b_r3_dev_r2_common import coverage_rows


def test_stratified_coverage_counts_overlapping_categories():
    cases = [SimpleNamespace(metadata_json={"is_model_case": True, "is_alarm_case": True, "is_vector_heavy": True, "is_no_answer": False, "relevance_cardinality": 2})]
    result = coverage_rows(cases)
    assert result["model_cases"] == result["alarm_cases"] == result["vector_heavy"] == 1
    assert result["multi_relevant"] == 1
