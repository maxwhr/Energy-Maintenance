from tests.integration.task25f_r1_artifacts import artifact


def test_historical_partial_failures_preserved_other_channels_and_current_run_recovers():
    value = artifact("semantic_failure_forensics.json")
    assert value["original_failure_count"] == 21
    assert all(item["fallback_result"] == "SAFE_PARTIAL_CHANNEL_DEGRADATION" for item in value["rows"])
    assert value["current_post_retry_failure_count"] == 0
