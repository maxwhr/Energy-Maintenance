from tests.integration.task25f_r1_artifacts import artifact


def test_all_60_cases_have_exact_candidate_parity_without_provider_calls():
    value = artifact("replay_parity.json")
    assert value["case_count"] == 60
    assert value["field_parity"]["candidate_identities"] == 1.0
    assert value["field_parity"]["rrf_order"] == 1.0
    assert value["provider_calls_during_replay"] == 0
