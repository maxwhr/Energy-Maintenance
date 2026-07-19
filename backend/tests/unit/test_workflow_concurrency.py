from app.models import MaintenanceWorkflow, MaintenanceWorkflowEvent


def test_database_constraints_cover_active_case_and_write_idempotency():
    workflow_indexes = {item.name for item in MaintenanceWorkflow.__table__.indexes}
    event_constraints = {item.name for item in MaintenanceWorkflowEvent.__table__.constraints}
    assert "uq_maintenance_workflows_active_case" in workflow_indexes
    assert "uq_workflow_event_idempotency" in event_constraints

