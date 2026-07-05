from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AgentEventLog, AgentStep, User
from app.repositories.agent_repository import AgentRepository


class AgentOrchestratorError(ValueError):
    pass


class BaseAgentOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AgentRepository(db)

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def create_step(
        self,
        *,
        run_id: str,
        step_index: int,
        step_type: str,
        step_name: str,
        status: str,
        input_json: dict[str, Any] | None = None,
        output_json: dict[str, Any] | None = None,
        reasoning_summary: str | None = None,
        error_message: str | None = None,
    ) -> AgentStep:
        now = self.now()
        step = self.repository.create_step(
            AgentStep(
                run_id=run_id,
                step_index=step_index,
                step_type=step_type,
                step_name=step_name,
                status=status,
                input_json=input_json,
                output_json=output_json,
                reasoning_summary=reasoning_summary,
                error_message=error_message,
                started_at=now,
                finished_at=now if status != "running" else None,
            )
        )
        self.db.commit()
        return step

    def create_event(
        self,
        *,
        run_id: str,
        event_type: str,
        event_message: str,
        payload_json: dict[str, Any] | None,
        current_user: User,
    ) -> None:
        self.repository.create_event(
            AgentEventLog(
                run_id=run_id,
                event_type=event_type,
                event_message=event_message,
                payload_json=payload_json,
                created_by=current_user.id,
            )
        )
        self.db.commit()
