import os
import pytest


@pytest.mark.skipif(os.getenv("R5_R1_RUN_REAL_TESTS") != "true", reason="run controlled rerank probe script explicitly")
def test_real_structured_rerank_is_covered_by_probe_artifact():
    pytest.skip("Use scripts/check_task25b_r3_dev_r5_r1_rerank_probe.py --allow-real-api")
