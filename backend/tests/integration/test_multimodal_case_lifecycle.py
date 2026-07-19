from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import User
from app.schemas.multimodal_case import MultimodalAnalyzeRequest, MultimodalCaseCreate
from app.services.multimodal_case_orchestrator_service import MultimodalCaseOrchestratorService
from app.services.multimodal_case_state_service import MultimodalCaseStateService


def test_text_only_case_reaches_evidence_ready_without_external_calls() -> None:
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        user = db.scalar(select(User).where(User.role == "engineer"))
        assert user is not None
        state = MultimodalCaseStateService(db)
        created = state.create(MultimodalCaseCreate(
            title="Task25C lifecycle transaction test",
            user_query="SUN2000 告警代码 2064 如何核对",
            idempotency_key="task25c-lifecycle-transaction-test",
        ), user)
        case = state.get(created.case_id, user)

        result = MultimodalCaseOrchestratorService(db).analyze(
            case,
            MultimodalAnalyzeRequest(dry_run=True, mock_run=False, allow_real_api=False),
            user,
        )

        assert result["job_status"] == "SUCCEEDED"
        assert result["case_status"] == "EVIDENCE_READY"
        assert result["external_api_called"] is False
        assert result["dedicated_rerank"] == "DEFERRED_QWEN3_RERANK_CONFIG"
        assert result["evidence_count"] >= 1
    finally:
        db.close()
        transaction.rollback()
        connection.close()
