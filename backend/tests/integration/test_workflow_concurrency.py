from app.main import app


def test_workflow_openapi_exposes_single_explicit_write_chain():
    paths = app.openapi()["paths"]
    required = {
        "/api/maintenance-workflows/{workflow_id}/diagnosis-confirm",
        "/api/maintenance-workflows/{workflow_id}/sop-review",
        "/api/maintenance-workflows/{workflow_id}/formal-task",
        "/api/maintenance-workflows/{workflow_id}/task/complete",
        "/api/maintenance-workflows/{workflow_id}/correction-candidate",
    }
    assert required <= set(paths)

