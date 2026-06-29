from __future__ import annotations

from datetime import datetime, timezone

from app.models import MaintenanceTask, SOPExecutionRecord, User


class TaskWorkflowServiceError(ValueError):
    pass


class TaskWorkflowService:
    ASSIGNABLE_ROLES = {"admin", "expert", "engineer"}

    def can_write_task(self, task: MaintenanceTask, current_user: User) -> bool:
        if current_user.role in {"admin", "expert"}:
            return True
        if current_user.role == "engineer":
            return task.assignee_id == current_user.id or task.created_by == current_user.id
        return False

    def can_start_task(self, task: MaintenanceTask, current_user: User) -> bool:
        if current_user.role in {"admin", "expert"}:
            return True
        return current_user.role == "engineer" and (
            task.assignee_id == current_user.id or task.created_by == current_user.id
        )

    def can_complete_task(self, task: MaintenanceTask, current_user: User) -> bool:
        return self.can_start_task(task, current_user)

    def can_cancel_task(self, task: MaintenanceTask, current_user: User) -> bool:
        if current_user.role in {"admin", "expert"}:
            return True
        return current_user.role == "engineer" and task.status in {"pending", "assigned"} and (
            task.assignee_id == current_user.id or task.created_by == current_user.id
        )

    @staticmethod
    def normalize_status(task: MaintenanceTask) -> str:
        status = task.status or task.task_status or "pending"
        if status == "new":
            return "pending"
        return status

    @staticmethod
    def set_status(task: MaintenanceTask, status: str) -> None:
        task.status = status
        task.task_status = status

    def assign(self, task: MaintenanceTask) -> None:
        status = self.normalize_status(task)
        if status in {"completed", "cancelled"}:
            raise TaskWorkflowServiceError("Completed or cancelled task cannot be reassigned")
        if status not in {"pending", "assigned"}:
            raise TaskWorkflowServiceError("Only pending or assigned task can be reassigned")
        self.set_status(task, "assigned")

    def start(self, task: MaintenanceTask, current_user: User) -> None:
        if not self.can_start_task(task, current_user):
            raise TaskWorkflowServiceError("Permission denied for starting this task")
        status = self.normalize_status(task)
        if status not in {"pending", "assigned"}:
            raise TaskWorkflowServiceError("Only pending or assigned task can be started")
        if current_user.role == "engineer" and task.assignee_id is None:
            task.assignee_id = current_user.id
            task.assignee = current_user.display_name or current_user.username
        self.set_status(task, "in_progress")

    def complete(self, task: MaintenanceTask, current_user: User) -> None:
        if not self.can_complete_task(task, current_user):
            raise TaskWorkflowServiceError("Permission denied for completing this task")
        status = self.normalize_status(task)
        if status == "cancelled":
            raise TaskWorkflowServiceError("Cancelled task cannot be completed")
        if status == "completed":
            raise TaskWorkflowServiceError("Task is already completed")
        if status != "in_progress":
            raise TaskWorkflowServiceError("Only in-progress task can be completed")
        self.set_status(task, "completed")
        task.completed_by = current_user.id

    def cancel(self, task: MaintenanceTask, current_user: User) -> None:
        if not self.can_cancel_task(task, current_user):
            raise TaskWorkflowServiceError("Permission denied for cancelling this task")
        status = self.normalize_status(task)
        if status == "completed":
            raise TaskWorkflowServiceError("Completed task cannot be cancelled")
        if status == "cancelled":
            raise TaskWorkflowServiceError("Task is already cancelled")
        self.set_status(task, "cancelled")

    @staticmethod
    def sync_sop_on_start(execution: SOPExecutionRecord | None) -> None:
        if not execution or execution.status in {"completed", "aborted"}:
            return
        execution.status = "in_progress"
        if execution.started_at is None:
            execution.started_at = datetime.now(timezone.utc)

    @staticmethod
    def sync_sop_on_complete(execution: SOPExecutionRecord | None) -> None:
        if not execution or execution.status == "aborted":
            return
        execution.status = "completed"
        if execution.started_at is None:
            execution.started_at = datetime.now(timezone.utc)
        if execution.completed_at is None:
            execution.completed_at = datetime.now(timezone.utc)

    @staticmethod
    def allowed_transitions(task: MaintenanceTask, current_user: User) -> list[str]:
        status = task.status or task.task_status or "pending"
        transitions: list[str] = []
        if current_user.role == "viewer":
            return transitions
        if status in {"pending", "assigned"}:
            transitions.append("start")
        if status == "in_progress":
            transitions.append("complete")
        if status != "completed":
            transitions.append("cancel")
        if current_user.role in {"admin", "expert"} and status in {"pending", "assigned"}:
            transitions.append("assign")
        return transitions
