from tests.integration.task25f_r1_artifacts import artifact


def test_parallel_and_sequential_outputs_match_all_hard_fields():
    value = artifact("replay_parity.json")
    assert value["passed"] is True
    assert value["first_divergent_stage_counts"] == {}
    assert all(item["passed"] for item in value["comparisons"])
