from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.multimodal_case_orchestrator_service import (
    MultimodalCaseOrchestratorError,
    MultimodalCaseOrchestratorService,
)


def test_real_provider_requires_explicit_task25c_gate() -> None:
    service = object.__new__(MultimodalCaseOrchestratorService)
    service.settings = SimpleNamespace(TASK25C_ALLOW_REAL_API=False)

    with pytest.raises(MultimodalCaseOrchestratorError, match="TASK25C_ALLOW_REAL_API"):
        service._require_real_provider_authorization(SimpleNamespace(role="admin"))
