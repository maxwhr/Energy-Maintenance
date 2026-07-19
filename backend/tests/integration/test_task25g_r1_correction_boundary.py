import inspect

from app.services.workflow_correction_service import WorkflowCorrectionService


def test_workflow_correction_creates_review_candidate_without_graph_write():
    source = inspect.getsource(WorkflowCorrectionService)
    assert "ModelOutputCorrection(" in source
    assert '"automatic_knowledge_update": False' in source
    assert '"expert_verified": False' in source
    for forbidden in ("KGNode(", "KGEdge(", "KGEvidenceLink(", "approve_candidate("):
        assert forbidden not in source

