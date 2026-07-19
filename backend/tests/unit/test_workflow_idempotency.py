from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.maintenance_workflow_service import MaintenanceWorkflowPermissionError
from app.services.maintenance_workflow_service import MaintenanceWorkflowService
from app.schemas.maintenance_workflow import DiagnosisDraftRequest
from app.services.workflow_diagnosis_service import WorkflowDiagnosisService


def test_idempotent_replay_returns_saved_result_without_new_write():
    service = MaintenanceWorkflowService(Mock())
    service.repository.get_event_by_idempotency = Mock(
        return_value=SimpleNamespace(result_json={"workflow_id": "mwf-1"})
    )
    result = service.idempotent_replay(
        SimpleNamespace(workflow_id="mwf-1"), "CREATE_TASK_DRAFT", "idem-0001"
    )
    assert result == {"workflow_id": "mwf-1", "idempotent_replay": True}


def test_terminal_replay_permission_keeps_rbac_but_allows_saved_result_lookup():
    service = MaintenanceWorkflowService(Mock())
    service.ensure_read_access = Mock()
    terminal = SimpleNamespace(status="COMPLETED")

    service.ensure_write_access(
        terminal,
        SimpleNamespace(role="engineer"),
        allow_terminal_replay=True,
    )

    with pytest.raises(MaintenanceWorkflowPermissionError):
        service.ensure_write_access(
            terminal,
            SimpleNamespace(role="viewer"),
            allow_terminal_replay=True,
        )


def test_terminal_diagnosis_request_replays_before_terminal_mutation_gate():
    service = WorkflowDiagnosisService(Mock())
    workflow = SimpleNamespace(workflow_id="mwf-closed", status="COMPLETED")
    user = SimpleNamespace(role="engineer")
    service.workflows.get = Mock(return_value=workflow)
    service.workflows.ensure_write_access = Mock()
    service.workflows.idempotent_replay = Mock(
        return_value={"workflow_id": "mwf-closed", "idempotent_replay": True}
    )

    result = service.create_draft(
        "mwf-closed",
        DiagnosisDraftRequest(idempotency_key="idem-terminal-0001"),
        user,
    )

    assert result["idempotent_replay"] is True
    service.workflows.ensure_write_access.assert_called_once_with(
        workflow,
        user,
        allow_terminal_replay=True,
    )
