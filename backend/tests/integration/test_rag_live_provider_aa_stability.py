from tests.integration.task25f_r1_artifacts import artifact


def test_real_provider_aa_is_explicitly_precomputed_not_called_by_pytest():
    value = artifact("provider_aa_stability.json")
    assert value["case_count"] == 30
    assert value["repetitions"] == 3
    assert value["raw_vector"]["exact_candidate_set_parity"] == 1.0
    assert value["semantic_unit"]["exact_candidate_set_parity"] == 1.0
    assert value["post_retry_failure_count"] == 0
