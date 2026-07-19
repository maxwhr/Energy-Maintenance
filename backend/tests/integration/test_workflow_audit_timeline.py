from app.models import MaintenanceWorkflowEvent


def test_workflow_event_contract_contains_actor_before_after_and_reason():
    columns = set(MaintenanceWorkflowEvent.__table__.columns.keys())
    assert {"actor_id", "actor_role", "before_json", "after_json", "reason", "created_at"} <= columns

