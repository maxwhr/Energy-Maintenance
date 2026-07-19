from tests.unit.test_semantic_unit_retry_policy import test_transient_connect_error_is_retried_once as _retry_contract


def test_transient_retry_integration_contract(monkeypatch):
    _retry_contract(monkeypatch)
