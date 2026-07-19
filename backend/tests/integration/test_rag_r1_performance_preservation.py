from tests.integration.task25f_r1_artifacts import artifact


def test_r1_performance_hard_gates_pass():
    value = artifact("performance_preservation.json")
    assert value["passed"] is True
    assert all(value["checks"].values())
