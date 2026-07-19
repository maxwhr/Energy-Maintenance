from __future__ import annotations

from app.services.multimodal_case_state_service import MultimodalCaseStateService


def test_case_state_machine_forbids_direct_formal_task_jump() -> None:
    assert "TASK_DRAFT_READY" not in MultimodalCaseStateService.TRANSITIONS["DRAFT"]
    assert "DIAGNOSIS_READY" not in MultimodalCaseStateService.TRANSITIONS["DRAFT"]
    assert MultimodalCaseStateService.TRANSITIONS["ARCHIVED"] == set()


def test_failed_case_has_explicit_recovery_paths() -> None:
    assert {"DRAFT", "MEDIA_UPLOADED", "ANALYZING"}.issubset(
        MultimodalCaseStateService.TRANSITIONS["FAILED"]
    )


def test_every_nonterminal_state_can_be_archived() -> None:
    for status, targets in MultimodalCaseStateService.TRANSITIONS.items():
        if status != "ARCHIVED":
            assert "ARCHIVED" in targets
