from pathlib import Path


def test_benchmark_label_integrity_has_non_valid_classifications():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "check_task25b_r3_dev_r1_benchmark_label_integrity.py").read_text(encoding="utf-8")
    for value in ("STALE_CHUNK_ID", "SUPERSEDED_CHUNK", "MODEL_LABEL_ERROR", "ALARM_LABEL_ERROR", "AMBIGUOUS"):
        assert value in source
