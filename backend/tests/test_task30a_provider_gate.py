from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.external_api_gateway import ExternalApiGateway, ExternalApiGatewayError


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> ExternalApiGateway:
    monkeypatch.setenv("TASK30A_ALLOW_REAL_PROVIDER", "true")
    monkeypatch.setenv("TASK30A_ALLOW_TEST_DB_WRITES", "true")
    monkeypatch.setenv("TASK30A_MAX_REAL_PROVIDER_CALLS", "16")
    service = ExternalApiGateway(MagicMock())
    service.repository.current_database = MagicMock(return_value="energy_maintenance_task30a_test")
    service.repository.acquire_real_call_budget_lock = MagicMock()
    service.repository.count_real_call_attempts = MagicMock(return_value=15)
    return service


def test_task30a_allows_sixteenth_attempt(gateway: ExternalApiGateway) -> None:
    gateway._enforce_task30a_real_call_gate({"task_id": "task30a", "image_id": "safe-sample"})
    gateway.repository.acquire_real_call_budget_lock.assert_called_once_with("task30a")


def test_task30a_blocks_seventeenth_attempt(gateway: ExternalApiGateway) -> None:
    gateway.repository.count_real_call_attempts.return_value = 16
    with pytest.raises(ExternalApiGatewayError, match="TASK30A_PROVIDER_CALL_BUDGET_EXCEEDED"):
        gateway._enforce_task30a_real_call_gate({"task_id": "task30a", "image_id": "safe-sample"})


def test_task30a_rejects_wrong_database(gateway: ExternalApiGateway) -> None:
    gateway.repository.current_database.return_value = "energy_maintenance"
    with pytest.raises(ExternalApiGatewayError, match="TASK30A_SECURITY_BOUNDARY_VIOLATION"):
        gateway._enforce_task30a_real_call_gate({"task_id": "task30a"})


def test_task30a_rejects_unmarked_request(gateway: ExternalApiGateway) -> None:
    with pytest.raises(ExternalApiGatewayError, match="TASK30A_SECURITY_BOUNDARY_VIOLATION"):
        gateway._enforce_task30a_real_call_gate({"image_id": "safe-sample"})


def test_task30a_requires_write_opt_in(gateway: ExternalApiGateway, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASK30A_ALLOW_TEST_DB_WRITES", "false")
    with pytest.raises(ExternalApiGatewayError, match="TASK30A_BLOCKED_EXPLICIT_APPROVAL_REQUIRED"):
        gateway._enforce_task30a_real_call_gate({"task_id": "task30a"})
