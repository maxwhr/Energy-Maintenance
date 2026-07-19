from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.multimodal_case_orchestrator_service import MultimodalCaseOrchestratorService
from app.services.multimodal_case_state_service import MultimodalCasePermissionError, MultimodalCaseStateService


def test_viewer_cannot_edit_and_non_owner_cannot_read() -> None:
    viewer = SimpleNamespace(role="viewer", id=uuid4())
    owner = uuid4()
    case = SimpleNamespace(created_by=owner)

    with pytest.raises(MultimodalCasePermissionError):
        MultimodalCaseOrchestratorService._require_editor(viewer)
    with pytest.raises(MultimodalCasePermissionError):
        MultimodalCaseStateService._require_access(case, viewer)


def test_expert_can_read_cross_owner_case() -> None:
    expert = SimpleNamespace(role="expert", id=uuid4())
    case = SimpleNamespace(created_by=uuid4())

    MultimodalCaseStateService._require_access(case, expert)
