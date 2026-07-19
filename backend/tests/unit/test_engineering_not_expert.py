from app.services.development_engineering_approval_service import DevelopmentEngineeringApprovalService


def test_engineering_reviewer_is_not_presented_as_expert():
    assert DevelopmentEngineeringApprovalService.actor == "Development Engineering Reviewer"
    assert "Expert" not in DevelopmentEngineeringApprovalService.actor
