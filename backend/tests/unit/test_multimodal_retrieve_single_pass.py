from __future__ import annotations

import inspect

from app.services.multimodal_case_orchestrator_service import MultimodalCaseOrchestratorService


def test_multimodal_retrieve_executes_one_query_aware_search() -> None:
    source = inspect.getsource(MultimodalCaseOrchestratorService.retrieve)

    assert source.count("QueryAwareRetrievalService(self.db, current_user=user).search") == 1
    assert "CrossModalRetrievalService" not in source
    assert "persist_result=payload.persist_result" in source
    assert "qa_response.citations or qa_response.references" in source
