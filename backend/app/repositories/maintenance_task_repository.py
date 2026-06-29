from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Device, DiagnosisRecord, MaintenanceTask, SOPExecutionRecord, SOPTemplate, User


class MaintenanceTaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: UUID) -> MaintenanceTask | None:
        statement = (
            select(MaintenanceTask)
            .where(MaintenanceTask.id == task_id)
            .options(selectinload(MaintenanceTask.device))
        )
        return self.db.scalar(statement)

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def get_user(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def list_assignable_users(self) -> list[User]:
        statement = (
            select(User)
            .where(
                User.role.in_(["admin", "expert", "engineer"]),
                User.status == "active",
                User.is_active.is_(True),
            )
            .order_by(User.role.asc(), User.username.asc())
        )
        return list(self.db.scalars(statement))

    def get_diagnosis_by_trace_id(self, trace_id: str) -> DiagnosisRecord | None:
        statement = select(DiagnosisRecord).where(DiagnosisRecord.trace_id == trace_id)
        return self.db.scalar(statement)

    def get_sop_template(self, template_id: UUID) -> SOPTemplate | None:
        return self.db.get(SOPTemplate, template_id)

    def get_sop_execution(self, execution_id: UUID) -> SOPExecutionRecord | None:
        return self.db.get(SOPExecutionRecord, execution_id)

    def list_tasks(
        self,
        *,
        device_id: UUID | None = None,
        assignee_id: UUID | None = None,
        status: str | None = None,
        priority: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        keyword: str | None = None,
        visible_user: User | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MaintenanceTask], int]:
        filters = []
        if device_id:
            filters.append(MaintenanceTask.device_id == device_id)
        if assignee_id:
            filters.append(MaintenanceTask.assignee_id == assignee_id)
        if status:
            filters.append(MaintenanceTask.status == status)
        if priority:
            filters.append(MaintenanceTask.priority == priority)
        if fault_type:
            filters.append(MaintenanceTask.fault_type == fault_type)
        if alarm_code:
            filters.append(MaintenanceTask.alarm_code.ilike(f"%{alarm_code}%"))
        if manufacturer:
            filters.append(MaintenanceTask.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(MaintenanceTask.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    MaintenanceTask.title.ilike(pattern),
                    MaintenanceTask.device_name.ilike(pattern),
                    MaintenanceTask.model.ilike(pattern),
                    MaintenanceTask.fault_description.ilike(pattern),
                    MaintenanceTask.alarm_code.ilike(pattern),
                    MaintenanceTask.assignee.ilike(pattern),
                )
            )
        if visible_user and visible_user.role == "engineer":
            filters.append(
                or_(
                    MaintenanceTask.assignee_id == visible_user.id,
                    MaintenanceTask.created_by == visible_user.id,
                )
            )

        count_statement = select(func.count()).select_from(MaintenanceTask)
        list_statement = (
            select(MaintenanceTask)
            .options(selectinload(MaintenanceTask.device))
            .order_by(MaintenanceTask.updated_at.desc(), MaintenanceTask.created_at.desc())
        )
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        tasks = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return tasks, total

    def create(self, task: MaintenanceTask) -> MaintenanceTask:
        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        return task

    def update(self, task: MaintenanceTask) -> MaintenanceTask:
        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        return task

    def statistics(self, *, current_user: User) -> dict[str, int]:
        base_filters = []
        my_filters = [
            or_(
                MaintenanceTask.assignee_id == current_user.id,
                MaintenanceTask.created_by == current_user.id,
            )
        ]
        if current_user.role == "engineer":
            base_filters.extend(my_filters)

        def count_for(*extra_filters) -> int:
            statement = select(func.count()).select_from(MaintenanceTask)
            filters = [*base_filters, *extra_filters]
            if filters:
                statement = statement.where(*filters)
            return self.db.scalar(statement) or 0

        my_statement = select(func.count()).select_from(MaintenanceTask).where(*my_filters)
        return {
            "total_tasks": count_for(),
            "pending_tasks": count_for(MaintenanceTask.status == "pending"),
            "assigned_tasks": count_for(MaintenanceTask.status == "assigned"),
            "in_progress_tasks": count_for(MaintenanceTask.status == "in_progress"),
            "completed_tasks": count_for(MaintenanceTask.status == "completed"),
            "cancelled_tasks": count_for(MaintenanceTask.status == "cancelled"),
            "high_priority_tasks": count_for(MaintenanceTask.priority.in_(["high", "urgent"])),
            "my_tasks": self.db.scalar(my_statement) or 0,
        }
