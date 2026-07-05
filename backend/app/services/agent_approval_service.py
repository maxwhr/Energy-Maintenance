from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AgentEventLog, User
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentApprovalRead


class AgentApprovalServiceError(ValueError):
    pass


class AgentApprovalPermissionError(PermissionError):
    pass


class AgentApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AgentRepository(db)

    def approve(self, approval_id: UUID, *, current_user: User, comment: str | None = None) -> AgentApprovalRead:
        return self._review(approval_id, current_user=current_user, next_status="approved", comment=comment)

    def reject(self, approval_id: UUID, *, current_user: User, comment: str | None = None) -> AgentApprovalRead:
        return self._review(approval_id, current_user=current_user, next_status="rejected", comment=comment)

    def _review(
        self,
        approval_id: UUID,
        *,
        current_user: User,
        next_status: str,
        comment: str | None,
    ) -> AgentApprovalRead:
        if current_user.role not in {"admin", "expert"}:
            raise AgentApprovalPermissionError("Only admin or expert can review agent approvals")
        approval = self.repository.get_approval(approval_id)
        if not approval:
            raise AgentApprovalServiceError("Agent approval not found")
        if approval.status != "pending":
            raise AgentApprovalServiceError("Only pending approvals can be reviewed")
        approval.status = next_status
        approval.reviewed_by = current_user.id
        approval.review_comment = comment
        approval.reviewed_at = datetime.now(timezone.utc)
        self.repository.update_approval(approval)
        run = self.repository.get_run(approval.run_id)
        if run:
            run.approval_status = next_status
            run.status = "blocked" if next_status == "rejected" else "succeeded"
            run.finished_at = datetime.now(timezone.utc)
            if next_status == "approved" and not run.final_answer:
                run.final_answer = "人工审批已通过，当前 Agent Runtime 仅记录审批结果，不直接执行高风险写入动作。"
            if next_status == "rejected":
                run.error_code = "approval_rejected"
                run.error_message = comment or "Agent approval was rejected"
            self.repository.update_run(run)
        self.repository.create_event(
            AgentEventLog(
                run_id=approval.run_id,
                event_type=f"approval_{next_status}",
                event_message=f"Agent approval {next_status}",
                payload_json={"approval_id": str(approval.id), "comment": comment},
                created_by=current_user.id,
            )
        )
        self.db.commit()
        return AgentApprovalRead.model_validate(approval)
