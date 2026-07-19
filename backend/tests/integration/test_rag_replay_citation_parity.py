from tests.integration.task25f_r1_artifacts import artifact


def test_replay_citation_identity_and_locator_are_exact():
    parity = artifact("replay_parity.json")["field_parity"]
    assert parity["citation_identities"] == 1.0
    assert parity["citation_locators"] == 1.0
