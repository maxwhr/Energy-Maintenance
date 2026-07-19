from tests.integration.task25f_r1_artifacts import artifact


def test_replay_top5_and_top10_are_exact():
    parity = artifact("replay_parity.json")["field_parity"]
    assert parity["top5_identities"] == 1.0
    assert parity["top10_identities"] == 1.0
