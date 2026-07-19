from app.services.multimodal_sop_task_boundary_service import MultimodalSopTaskBoundaryService


def test_sop_is_draft_only_and_requires_grounding() -> None:
    service = MultimodalSopTaskBoundaryService()
    blocked = service.allow_sop_draft(
        device_model=None,
        user_confirmed_device=False,
        valid_citation_count=0,
        safety_complete=False,
        evidence_confidence=0.4,
        open_high_conflicts=1,
    )
    allowed = service.allow_sop_draft(
        device_model="SUN2000-100KTL-M2",
        user_confirmed_device=True,
        valid_citation_count=2,
        safety_complete=True,
        evidence_confidence=0.9,
        open_high_conflicts=0,
    )

    assert blocked.allowed is False
    assert allowed.allowed is True
    assert allowed.artifact_type == "sop_draft"
    assert allowed.requires_human_approval is True
    assert allowed.formal_record_created is False
