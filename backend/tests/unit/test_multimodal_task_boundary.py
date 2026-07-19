from app.services.multimodal_sop_task_boundary_service import MultimodalSopTaskBoundaryService


def test_task_draft_never_creates_formal_task() -> None:
    service = MultimodalSopTaskBoundaryService()
    blocked = service.allow_task_draft(
        sop_status="draft",
        sop_user_confirmed=False,
        safety_complete=True,
        role="engineer",
    )
    allowed = service.allow_task_draft(
        sop_status="draft",
        sop_user_confirmed=True,
        safety_complete=True,
        role="engineer",
    )

    assert blocked.allowed is False
    assert allowed.allowed is True
    assert allowed.artifact_type == "task_draft"
    assert allowed.formal_record_created is False
