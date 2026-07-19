from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.external_api_gateway import ExternalApiGateway, ExternalApiGatewayError


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> ExternalApiGateway:
    values = {
        "TASK32A_ALLOW_REAL_PROVIDER": "true",
        "TASK32A_ALLOW_TEST_DB_WRITES": "true",
        "TASK32A_MAX_REAL_PROVIDER_CALLS": "4",
        "TASK32A_FORMAL_DB_ACCESS": "false",
        "TASK32A_ALLOW_EMBEDDING": "false",
        "TASK32A_ALLOW_VECTOR_REBUILD": "false",
        "TASK32A_GIT_OPERATIONS_ALLOWED": "false",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    service = ExternalApiGateway(MagicMock())
    service.repository.current_database = MagicMock(return_value="energy_maintenance_task32a_test")
    service.repository.acquire_real_call_budget_lock = MagicMock()
    service.repository.count_real_call_attempts = MagicMock(return_value=3)
    return service


def payload() -> dict:
    return {
        "task_id": "task32a",
        "approval_id": "APPROVE_TASK32A_FULL_SYSTEM_TEST_AND_FIX_V1",
        "image_id": "safe-sample",
    }


def test_task32a_allows_fourth_attempt(gateway: ExternalApiGateway) -> None:
    gateway._enforce_task30a_real_call_gate(payload())
    gateway.repository.acquire_real_call_budget_lock.assert_called_once_with("task32a")
    gateway.repository.count_real_call_attempts.assert_called_once_with("task32a")


def test_task32a_blocks_fifth_attempt(gateway: ExternalApiGateway) -> None:
    gateway.repository.count_real_call_attempts.return_value = 4
    with pytest.raises(ExternalApiGatewayError, match="TASK32A_PROVIDER_CALL_BUDGET_EXCEEDED"):
        gateway._enforce_task30a_real_call_gate(payload())


def test_task32a_rejects_formal_database(gateway: ExternalApiGateway) -> None:
    gateway.repository.current_database.return_value = "energy_maintenance"
    with pytest.raises(ExternalApiGatewayError, match="TASK32A_SECURITY_BOUNDARY_VIOLATION"):
        gateway._enforce_task30a_real_call_gate(payload())


def test_task32a_rejects_missing_approval_marker(gateway: ExternalApiGateway) -> None:
    with pytest.raises(ExternalApiGatewayError, match="TASK32A_SECURITY_BOUNDARY_VIOLATION"):
        gateway._enforce_task30a_real_call_gate({"task_id": "task32a"})


def test_task32a_requires_all_negative_gates(gateway: ExternalApiGateway, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASK32A_ALLOW_EMBEDDING", "true")
    with pytest.raises(ExternalApiGatewayError, match="TASK32A_BLOCKED_EXPLICIT_APPROVAL_REQUIRED"):
        gateway._enforce_task30a_real_call_gate(payload())
