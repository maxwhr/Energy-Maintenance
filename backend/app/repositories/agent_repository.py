from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentArtifactConversion,
    AgentDefinition,
    AgentEventLog,
    AgentRun,
    AgentStep,
    AgentTool,
    AgentToolCall,
)


class AgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_definition(self, values: dict) -> AgentDefinition:
        existing = self.get_definition(values["agent_code"])
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            self.db.flush()
            self.db.refresh(existing)
            return existing
        definition = AgentDefinition(**values)
        self.db.add(definition)
        self.db.flush()
        self.db.refresh(definition)
        return definition

    def get_definition(self, agent_code: str) -> AgentDefinition | None:
        return self.db.scalar(select(AgentDefinition).where(AgentDefinition.agent_code == agent_code))

    def list_definitions(self, *, enabled: bool | None = None) -> list[AgentDefinition]:
        statement = select(AgentDefinition).order_by(AgentDefinition.agent_code.asc())
        if enabled is not None:
            statement = statement.where(AgentDefinition.enabled == enabled)
        return list(self.db.scalars(statement))

    def upsert_tool(self, values: dict) -> AgentTool:
        existing = self.get_tool(values["tool_name"])
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            self.db.flush()
            self.db.refresh(existing)
            return existing
        tool = AgentTool(**values)
        self.db.add(tool)
        self.db.flush()
        self.db.refresh(tool)
        return tool

    def get_tool(self, tool_name: str) -> AgentTool | None:
        return self.db.scalar(select(AgentTool).where(AgentTool.tool_name == tool_name))

    def list_tools(self, *, enabled: bool | None = None) -> list[AgentTool]:
        statement = select(AgentTool).order_by(AgentTool.tool_type.asc(), AgentTool.tool_name.asc())
        if enabled is not None:
            statement = statement.where(AgentTool.enabled == enabled)
        return list(self.db.scalars(statement))

    def create_run(self, run: AgentRun) -> AgentRun:
        self.db.add(run)
        self.db.flush()
        self.db.refresh(run)
        return run

    def update_run(self, run: AgentRun) -> AgentRun:
        self.db.add(run)
        self.db.flush()
        self.db.refresh(run)
        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        return self.db.scalar(select(AgentRun).where(AgentRun.run_id == run_id))

    def list_runs(
        self,
        *,
        current_user_id: UUID | None = None,
        include_all: bool = False,
        status: str | None = None,
        agent_code: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentRun], int]:
        filters = []
        if not include_all:
            filters.append(AgentRun.user_id == current_user_id)
        if status:
            filters.append(AgentRun.status == status)
        if agent_code:
            filters.append(AgentRun.agent_code == agent_code)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(AgentRun.run_id.ilike(pattern), AgentRun.input_text.ilike(pattern)))

        count_statement = select(func.count()).select_from(AgentRun)
        list_statement = select(AgentRun).order_by(AgentRun.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        items = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return items, total

    def create_step(self, step: AgentStep) -> AgentStep:
        self.db.add(step)
        self.db.flush()
        self.db.refresh(step)
        return step

    def update_step(self, step: AgentStep) -> AgentStep:
        self.db.add(step)
        self.db.flush()
        self.db.refresh(step)
        return step

    def list_steps(self, run_id: str) -> list[AgentStep]:
        return list(
            self.db.scalars(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index.asc())
            )
        )

    def create_tool_call(self, call: AgentToolCall) -> AgentToolCall:
        self.db.add(call)
        self.db.flush()
        self.db.refresh(call)
        return call

    def update_tool_call(self, call: AgentToolCall) -> AgentToolCall:
        self.db.add(call)
        self.db.flush()
        self.db.refresh(call)
        return call

    def list_tool_calls(self, run_id: str) -> list[AgentToolCall]:
        return list(
            self.db.scalars(
                select(AgentToolCall)
                .where(AgentToolCall.run_id == run_id)
                .order_by(AgentToolCall.created_at.asc())
            )
        )

    def create_approval(self, approval: AgentApproval) -> AgentApproval:
        self.db.add(approval)
        self.db.flush()
        self.db.refresh(approval)
        return approval

    def get_approval(self, approval_id: UUID) -> AgentApproval | None:
        return self.db.get(AgentApproval, approval_id)

    def update_approval(self, approval: AgentApproval) -> AgentApproval:
        self.db.add(approval)
        self.db.flush()
        self.db.refresh(approval)
        return approval

    def list_approvals(self, run_id: str) -> list[AgentApproval]:
        return list(
            self.db.scalars(
                select(AgentApproval)
                .where(AgentApproval.run_id == run_id)
                .order_by(AgentApproval.created_at.asc())
            )
        )

    def create_artifact(self, artifact: AgentArtifact) -> AgentArtifact:
        self.db.add(artifact)
        self.db.flush()
        self.db.refresh(artifact)
        return artifact

    def list_artifacts(self, run_id: str) -> list[AgentArtifact]:
        return list(
            self.db.scalars(
                select(AgentArtifact)
                .where(AgentArtifact.run_id == run_id)
                .order_by(AgentArtifact.created_at.asc())
            )
        )

    def get_artifact(self, artifact_id: UUID) -> AgentArtifact | None:
        return self.db.get(AgentArtifact, artifact_id)

    def lock_artifact_for_conversion(self, artifact_id: UUID) -> AgentArtifact | None:
        return self.db.scalar(
            select(AgentArtifact)
            .where(AgentArtifact.id == artifact_id)
            .with_for_update()
        )

    def list_artifacts_by_ids(self, artifact_ids: list[UUID]) -> list[AgentArtifact]:
        if not artifact_ids:
            return []
        return list(
            self.db.scalars(
                select(AgentArtifact)
                .where(AgentArtifact.id.in_(artifact_ids))
                .order_by(AgentArtifact.created_at.asc())
            )
        )

    def create_event(self, event: AgentEventLog) -> AgentEventLog:
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def find_conversion_event(self, *, source_artifact_id: UUID, target_type: str) -> AgentEventLog | None:
        statement = (
            select(AgentEventLog)
            .where(
                AgentEventLog.event_type == "draft_converted_to_formal_object",
                AgentEventLog.payload_json.contains(
                    {
                        "source_artifact_id": str(source_artifact_id),
                        "target_type": target_type,
                    }
                ),
            )
            .order_by(AgentEventLog.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_conversion_by_artifact_and_target(
        self,
        source_artifact_id: UUID,
        target_type: str,
    ) -> AgentArtifactConversion | None:
        return self.db.scalar(
            select(AgentArtifactConversion).where(
                AgentArtifactConversion.source_artifact_id == source_artifact_id,
                AgentArtifactConversion.target_type == target_type,
            )
        )

    def get_conversion_by_trace_id(self, conversion_trace_id: str) -> AgentArtifactConversion | None:
        return self.db.scalar(
            select(AgentArtifactConversion).where(
                AgentArtifactConversion.conversion_trace_id == conversion_trace_id,
            )
        )

    def get_conversion_by_id(self, conversion_id: UUID) -> AgentArtifactConversion | None:
        return self.db.get(AgentArtifactConversion, conversion_id)

    def create_conversion_pending(self, conversion: AgentArtifactConversion) -> AgentArtifactConversion:
        self.db.add(conversion)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_conversion_by_artifact_and_target(
                conversion.source_artifact_id,
                conversion.target_type,
            )
            if existing:
                return existing
            raise
        self.db.refresh(conversion)
        return conversion

    def mark_conversion_converting(self, conversion: AgentArtifactConversion, *, started_at: datetime) -> AgentArtifactConversion:
        conversion.conversion_status = "converting"
        conversion.started_at = started_at
        self.db.add(conversion)
        self.db.flush()
        self.db.refresh(conversion)
        return conversion

    def mark_conversion_succeeded(
        self,
        conversion: AgentArtifactConversion,
        *,
        target_id: UUID,
        target_table: str,
        target_payload: dict | None,
        result_summary: dict | None,
        completed_at: datetime,
        converted_by: UUID | None,
    ) -> AgentArtifactConversion:
        conversion.target_id = target_id
        conversion.target_table = target_table
        conversion.target_payload_json = target_payload
        conversion.result_summary_json = result_summary
        conversion.conversion_status = "succeeded"
        conversion.completed_at = completed_at
        conversion.converted_by = converted_by
        conversion.error_message = None
        self.db.add(conversion)
        self.db.flush()
        self.db.refresh(conversion)
        return conversion

    def mark_conversion_failed(
        self,
        conversion: AgentArtifactConversion,
        *,
        error_message: str,
        failed_at: datetime,
    ) -> AgentArtifactConversion:
        conversion.conversion_status = "failed"
        conversion.error_message = error_message
        conversion.failed_at = failed_at
        self.db.add(conversion)
        self.db.flush()
        self.db.refresh(conversion)
        return conversion

    def mark_conversion_voided(
        self,
        conversion: AgentArtifactConversion,
        *,
        voided_by: UUID | None,
        voided_at: datetime,
        metadata: dict | None = None,
    ) -> AgentArtifactConversion:
        conversion.conversion_status = "voided"
        conversion.voided_by = voided_by
        conversion.voided_at = voided_at
        if metadata:
            conversion.metadata_json = {**(conversion.metadata_json or {}), **metadata}
        self.db.add(conversion)
        self.db.flush()
        self.db.refresh(conversion)
        return conversion

    def list_conversions(
        self,
        *,
        current_user_id: UUID | None = None,
        include_all: bool = False,
        target_type: str | None = None,
        conversion_status: str | None = None,
        source_run_id: UUID | None = None,
        source_artifact_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentArtifactConversion], int]:
        filters = []
        if not include_all:
            filters.append(AgentArtifactConversion.requested_by == current_user_id)
        if target_type:
            filters.append(AgentArtifactConversion.target_type == target_type)
        if conversion_status:
            filters.append(AgentArtifactConversion.conversion_status == conversion_status)
        if source_run_id:
            filters.append(AgentArtifactConversion.source_run_id == source_run_id)
        if source_artifact_id:
            filters.append(AgentArtifactConversion.source_artifact_id == source_artifact_id)

        count_statement = select(func.count()).select_from(AgentArtifactConversion)
        list_statement = select(AgentArtifactConversion).order_by(AgentArtifactConversion.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        items = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return items, total

    def get_conversions_for_run(self, source_run_id: UUID) -> list[AgentArtifactConversion]:
        return list(
            self.db.scalars(
                select(AgentArtifactConversion)
                .where(AgentArtifactConversion.source_run_id == source_run_id)
                .order_by(AgentArtifactConversion.created_at.desc())
            )
        )

    def get_conversions_for_artifact(self, artifact_id: UUID) -> list[AgentArtifactConversion]:
        return list(
            self.db.scalars(
                select(AgentArtifactConversion)
                .where(AgentArtifactConversion.source_artifact_id == artifact_id)
                .order_by(AgentArtifactConversion.created_at.desc())
            )
        )

    def get_conversion_event(self, conversion_trace_id: str) -> AgentEventLog | None:
        statement = (
            select(AgentEventLog)
            .where(
                AgentEventLog.event_type == "draft_converted_to_formal_object",
                AgentEventLog.payload_json.contains({"conversion_trace_id": conversion_trace_id}),
            )
            .order_by(AgentEventLog.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def list_conversion_events(
        self,
        *,
        current_user_id: UUID | None = None,
        include_all: bool = False,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentEventLog], int]:
        filters = [AgentEventLog.event_type == "draft_converted_to_formal_object"]
        if target_type:
            filters.append(AgentEventLog.payload_json.contains({"target_type": target_type}))
        if not include_all:
            filters.append(AgentEventLog.created_by == current_user_id)

        count_statement = select(func.count()).select_from(AgentEventLog).where(*filters)
        list_statement = (
            select(AgentEventLog)
            .where(*filters)
            .order_by(AgentEventLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = self.db.scalar(count_statement) or 0
        items = list(self.db.scalars(list_statement))
        return items, total

    def list_events(
        self,
        *,
        run_id: str | None = None,
        event_type: str | None = None,
        current_user_id: UUID | None = None,
        include_all: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentEventLog], int]:
        filters = []
        if run_id:
            filters.append(AgentEventLog.run_id == run_id)
        if event_type:
            filters.append(AgentEventLog.event_type == event_type)
        if not include_all:
            filters.append(AgentEventLog.created_by == current_user_id)

        count_statement = select(func.count()).select_from(AgentEventLog)
        list_statement = select(AgentEventLog).order_by(AgentEventLog.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        items = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return items, total
