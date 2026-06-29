from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Device, DiagnosisRecord, MaintenanceTask, SOPExecutionRecord, SOPTemplate, User
from app.repositories.maintenance_record_repository import MaintenanceRecordRepository
from app.repositories.maintenance_task_repository import MaintenanceTaskRepository
from app.schemas.device import DeviceRead
from app.schemas.diagnosis import DiagnosisRecordItem
from app.schemas.maintenance_task import (
    MaintenanceRecordFromTask,
    MaintenanceTaskAssignRequest,
    MaintenanceTaskCancelRequest,
    MaintenanceTaskCompleteRequest,
    MaintenanceTaskCreateRequest,
    MaintenanceTaskDetail,
    MaintenanceTaskRead,
    MaintenanceTaskStatistics,
    MaintenanceTaskUpdateRequest,
    TASK_PRIORITIES,
    TASK_STATUSES,
)
from app.schemas.sop import SOPExecutionRecordDetail, SOPTemplateRead
from app.services.maintenance_record_service import MaintenanceRecordService, MaintenanceRecordServiceError
from app.services.media_service import MediaService, MediaServiceError
from app.services.task_workflow_service import TaskWorkflowService, TaskWorkflowServiceError


class MaintenanceTaskServiceError(ValueError):
    pass


class MaintenanceTaskService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceTaskRepository(db)
        self.record_repository = MaintenanceRecordRepository(db)
        self.record_service = MaintenanceRecordService(self.record_repository)
        self.workflow = TaskWorkflowService()
        self.media_service = MediaService(db)

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
        page: int = 1,
        page_size: int = 20,
        current_user: User,
    ) -> dict:
        self._validate_page(page, page_size)
        if status:
            self._validate_status(status)
        if priority:
            self._validate_priority(priority)
        tasks, total = self.repository.list_tasks(
            device_id=device_id,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
            fault_type=fault_type,
            alarm_code=alarm_code,
            manufacturer=manufacturer,
            product_series=product_series,
            keyword=keyword,
            visible_user=current_user,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._task_payload(task) for task in tasks],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_detail(self, task_id: UUID, current_user: User) -> dict | None:
        task = self.repository.get_by_id(task_id)
        if not task:
            return None
        if current_user.role == "engineer" and not self.workflow.can_write_task(task, current_user):
            raise MaintenanceTaskServiceError("Permission denied for this task")
        return self._detail_payload(task, current_user)

    def create_task(self, payload: MaintenanceTaskCreateRequest, current_user: User) -> dict:
        if current_user.role == "viewer":
            raise MaintenanceTaskServiceError("Permission denied")
        self._validate_priority(payload.priority)

        device = self._resolve_device(payload.device_id)
        diagnosis = self._resolve_diagnosis(payload.diagnosis_trace_id)
        if device and diagnosis and diagnosis.device_id and diagnosis.device_id != device.id:
            raise MaintenanceTaskServiceError("Selected diagnosis record does not belong to selected device")
        if diagnosis and not device and diagnosis.device_id:
            device = self._resolve_device(diagnosis.device_id)

        sop_template = self._resolve_sop_template(payload.sop_template_id)
        sop_execution = self._resolve_sop_execution(payload.sop_execution_id)
        if sop_execution and not sop_template:
            sop_template = sop_execution.template
        assignee = self._resolve_assignee(payload.assignee_id)
        if current_user.role == "engineer" and assignee and assignee.id != current_user.id:
            raise MaintenanceTaskServiceError("Engineer cannot assign task to another user")

        task_data = self._task_data_from_context(payload, device, diagnosis, sop_template, sop_execution, assignee)
        task_data["created_by"] = current_user.id
        task = MaintenanceTask(**task_data)
        try:
            saved = self.repository.create(task)
            if sop_execution:
                sop_execution.task_id = saved.id
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(f"Maintenance task write failed: {exc}") from exc
        return self._task_payload(saved)

    def update_task(self, task_id: UUID, payload: MaintenanceTaskUpdateRequest, current_user: User) -> dict:
        task = self._get_task_or_error(task_id)
        if current_user.role == "viewer":
            raise MaintenanceTaskServiceError("Permission denied")
        if not self.workflow.can_write_task(task, current_user):
            raise MaintenanceTaskServiceError("Permission denied for this task")
        data = payload.model_dump(exclude_unset=True)
        if current_user.role == "engineer":
            forbidden = {"assignee_id"}
            if forbidden.intersection(data):
                raise MaintenanceTaskServiceError("Engineer cannot assign task to another user")
        if data.get("priority"):
            self._validate_priority(data["priority"])
        if "assignee_id" in data:
            assignee = self._resolve_assignee(data["assignee_id"])
            task.assignee_id = assignee.id if assignee else None
            task.assignee = self._user_name(assignee) if assignee else None
            if assignee and task.status == "pending":
                self.workflow.set_status(task, "assigned")
        if "sop_template_id" in data:
            template = self._resolve_sop_template(data["sop_template_id"])
            task.sop_template_id = template.id if template else None
        if "sop_execution_id" in data:
            execution = self._resolve_sop_execution(data["sop_execution_id"])
            task.sop_execution_id = execution.id if execution else None
            if execution:
                execution.task_id = task.id
        for field in ["title", "priority", "fault_type", "alarm_code", "fault_description", "remark"]:
            if field in data:
                if field == "remark":
                    task.completion_notes = data[field]
                else:
                    setattr(task, field, data[field])
        if "planned_end_at" in data:
            task.due_date = data["planned_end_at"]
        try:
            saved = self.repository.update(task)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(f"Maintenance task update failed: {exc}") from exc
        return self._task_payload(saved)

    def assign_task(self, task_id: UUID, payload: MaintenanceTaskAssignRequest, current_user: User) -> dict:
        if current_user.role not in {"admin", "expert"}:
            raise MaintenanceTaskServiceError("Only admin or expert can assign task")
        task = self._get_task_or_error(task_id)
        assignee = self._resolve_assignee(payload.assignee_id)
        if not assignee:
            raise MaintenanceTaskServiceError("Assignee not found")
        try:
            self.workflow.assign(task)
        except TaskWorkflowServiceError as exc:
            raise MaintenanceTaskServiceError(str(exc)) from exc
        task.assignee_id = assignee.id
        task.assignee = self._user_name(assignee)
        try:
            saved = self.repository.update(task)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(f"Maintenance task assignment failed: {exc}") from exc
        return self._task_payload(saved)

    def start_task(self, task_id: UUID, current_user: User) -> dict:
        task = self._get_task_or_error(task_id)
        try:
            execution = self._resolve_sop_execution(task.sop_execution_id) if task.sop_execution_id else None
            self.workflow.start(task, current_user)
            self.workflow.sync_sop_on_start(execution)
            saved = self.repository.update(task)
            self.db.commit()
            self.db.refresh(saved)
        except TaskWorkflowServiceError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(str(exc)) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(f"Maintenance task start failed: {exc}") from exc
        return self._task_payload(saved)

    def complete_task(self, task_id: UUID, payload: MaintenanceTaskCompleteRequest, current_user: User) -> dict:
        task = self._get_task_or_error(task_id)
        device = self._resolve_device(task.device_id)
        execution = self._resolve_sop_execution(task.sop_execution_id) if task.sop_execution_id else None
        try:
            media_items = self.media_service.resolve_media_items(
                payload.media_ids,
                device_id=task.device_id,
            )
            self.workflow.complete(task, current_user)
            task.root_cause = payload.root_cause
            task.repair_action = payload.repair_action
            task.replaced_parts = payload.replaced_parts
            task.verification_result = payload.verification_result
            task.is_recurrent = payload.is_recurrent
            task.completed_at = payload.completed_at or datetime.now(timezone.utc)
            task.completion_notes = payload.maintenance_record_remark
            record = self.record_service.ensure_record_from_task(
                task=task,
                device=device,
                payload=payload,
                current_user=current_user,
            )
            self.workflow.sync_sop_on_complete(execution)
            self.media_service.link_to_task(media_items, task.id)
            self.repository.update(task)
            self.db.commit()
            self.db.refresh(task)
            self.db.refresh(record)
        except (TaskWorkflowServiceError, MaintenanceRecordServiceError, MediaServiceError) as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(str(exc)) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(f"Maintenance task completion failed: {exc}") from exc
        return self._detail_payload(task, current_user)

    def cancel_task(self, task_id: UUID, payload: MaintenanceTaskCancelRequest, current_user: User) -> dict:
        task = self._get_task_or_error(task_id)
        try:
            self.workflow.cancel(task, current_user)
            task.completion_notes = payload.reason
            task.result_summary = f"Task cancelled: {payload.reason}"
            saved = self.repository.update(task)
            self.db.commit()
            self.db.refresh(saved)
        except TaskWorkflowServiceError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(str(exc)) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceTaskServiceError(f"Maintenance task cancellation failed: {exc}") from exc
        return self._task_payload(saved)

    def statistics(self, current_user: User) -> dict:
        return MaintenanceTaskStatistics(**self.repository.statistics(current_user=current_user)).model_dump()

    def list_assignable_users(self, current_user: User) -> list[dict]:
        if current_user.role not in {"admin", "expert"}:
            raise MaintenanceTaskServiceError("Only admin or expert can list assignable users")
        return [
            {
                "id": str(user.id),
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
            }
            for user in self.repository.list_assignable_users()
        ]

    def _task_data_from_context(
        self,
        payload: MaintenanceTaskCreateRequest,
        device: Device | None,
        diagnosis: DiagnosisRecord | None,
        sop_template: SOPTemplate | None,
        sop_execution: SOPExecutionRecord | None,
        assignee: User | None,
    ) -> dict:
        source_type = "manual"
        source_trace_id = None
        if diagnosis:
            source_type = "diagnosis"
            source_trace_id = diagnosis.trace_id
        elif payload.qa_trace_id:
            source_type = "qa"
            source_trace_id = payload.qa_trace_id

        fault_type = payload.fault_type or (diagnosis.fault_type if diagnosis else None)
        alarm_code = payload.alarm_code or (diagnosis.alarm_code if diagnosis else None)
        fault_description = payload.fault_description or (diagnosis.fault_description if diagnosis else None)
        suggested_steps = diagnosis.recommended_actions if diagnosis and diagnosis.recommended_actions else []
        title = payload.title or self._default_title(device, fault_type, alarm_code)
        status = "assigned" if assignee else "pending"
        return {
            "title": title,
            "manufacturer": device.manufacturer if device else (diagnosis.manufacturer if diagnosis else None),
            "product_series": device.product_series if device else (diagnosis.product_series if diagnosis else None),
            "device_type": "pv_inverter",
            "device_id": device.id if device else None,
            "device_name": device.device_name if device else (diagnosis.device_name if diagnosis else None),
            "model": device.model if device else (diagnosis.model if diagnosis else None),
            "fault_type": fault_type,
            "alarm_code": alarm_code,
            "fault_description": fault_description,
            "priority": payload.priority,
            "status": status,
            "task_status": status,
            "assignee_id": assignee.id if assignee else None,
            "assignee": self._user_name(assignee) if assignee else None,
            "due_date": payload.planned_end_at,
            "source_type": source_type,
            "source_trace_id": source_trace_id,
            "sop_template_id": sop_template.id if sop_template else None,
            "sop_execution_id": sop_execution.id if sop_execution else None,
            "suggested_steps": suggested_steps,
            "completion_notes": payload.remark,
        }

    def _detail_payload(self, task: MaintenanceTask, current_user: User) -> dict:
        device = self._resolve_device(task.device_id)
        diagnosis = self._resolve_diagnosis(task.source_trace_id) if task.source_type == "diagnosis" and task.source_trace_id else None
        template = self._resolve_sop_template(task.sop_template_id, allow_archived=True) if task.sop_template_id else None
        execution = self._resolve_sop_execution(task.sop_execution_id) if task.sop_execution_id else None
        maintenance_record = self.record_repository.get_by_task_id(task.id)
        media_items = self._task_media(task, diagnosis)
        return MaintenanceTaskDetail(
            task=MaintenanceTaskRead(**self._task_payload(task)),
            device=DeviceRead.model_validate(device).model_dump(mode="json") if device else None,
            diagnosis_record=self._diagnosis_payload(diagnosis) if diagnosis else None,
            sop_template=SOPTemplateRead.model_validate(template).model_dump(mode="json") if template else None,
            sop_execution=SOPExecutionRecordDetail.model_validate(execution).model_dump(mode="json") if execution else None,
            maintenance_record=MaintenanceRecordFromTask.model_validate(maintenance_record).model_dump(mode="json") if maintenance_record else None,
            media_items=[self.media_service.media_context(item) for item in media_items],
            media_notice=(
                "任务关联图片仅作为现场与完工证据；当前未启用 OCR/图像识别。"
                if media_items
                else None
            ),
            allowed_transitions=self.workflow.allowed_transitions(task, current_user),
            field_limitations=[
                "maintenance_tasks has no started_at column; started_at is returned as null.",
                "maintenance_tasks has no cancelled_at or metadata_json column; cancellation reason is stored in completion_notes/result_summary.",
                "planned_start_at is not persisted because the current table has no matching column.",
            ],
        ).model_dump(mode="json")

    def _task_media(
        self,
        task: MaintenanceTask,
        diagnosis: DiagnosisRecord | None,
    ) -> list:
        result = self.media_service.list_media(task_id=task.id, page=1, page_size=100)["items"]
        if diagnosis and diagnosis.media_ids:
            try:
                result.extend(
                    self.media_service.resolve_media_items(
                        [UUID(str(item)) for item in diagnosis.media_ids],
                        device_id=task.device_id,
                    )
                )
            except (ValueError, MediaServiceError):
                pass
        unique = {}
        for item in result:
            unique[item.id] = item
        return list(unique.values())

    def _task_payload(self, task: MaintenanceTask) -> dict:
        assignee = self.repository.get_user(task.assignee_id) if task.assignee_id else None
        creator = self.repository.get_user(task.created_by) if task.created_by else None
        device = task.device or (self._resolve_device(task.device_id) if task.device_id else None)
        status = task.status or task.task_status or "pending"
        source_trace = task.source_trace_id
        replaced_parts = task.replaced_parts or []
        return MaintenanceTaskRead(
            id=task.id,
            task_code=f"MT-{str(task.id)[:8].upper()}",
            title=task.title,
            device_id=task.device_id,
            device_name=task.device_name,
            device_code=device.device_code if device else None,
            manufacturer=task.manufacturer,
            product_series=task.product_series,
            model=task.model,
            device_type=task.device_type,
            fault_type=task.fault_type,
            alarm_code=task.alarm_code,
            fault_description=task.fault_description,
            priority=task.priority,
            status=status,
            task_status=task.task_status or status,
            assignee_id=task.assignee_id,
            assignee_name=self._user_name(assignee) if assignee else task.assignee,
            created_by=task.created_by,
            created_by_name=self._user_name(creator) if creator else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=None,
            completed_at=task.completed_at,
            cancelled_at=task.updated_at if status == "cancelled" else None,
            planned_start_at=None,
            planned_end_at=task.due_date,
            sop_template_id=task.sop_template_id,
            sop_execution_id=task.sop_execution_id,
            diagnosis_trace_id=source_trace if task.source_type == "diagnosis" else None,
            qa_trace_id=source_trace if task.source_type == "qa" else None,
            source_type=task.source_type,
            root_cause=task.root_cause,
            repair_action=task.repair_action,
            replaced_parts=[str(item) for item in replaced_parts],
            verification_result=task.verification_result,
            is_recurrent=task.is_recurrent,
            completion_notes=task.completion_notes,
        ).model_dump(mode="json")

    @staticmethod
    def _diagnosis_payload(diagnosis: DiagnosisRecord) -> dict:
        summary = diagnosis.fault_description[:160] if diagnosis.fault_description else ""
        return DiagnosisRecordItem(
            id=diagnosis.id,
            trace_id=diagnosis.trace_id,
            device_id=diagnosis.device_id,
            device_name=diagnosis.device_name,
            manufacturer=diagnosis.manufacturer,
            product_series=diagnosis.product_series,
            model=diagnosis.model,
            device_type=diagnosis.device_type,
            fault_type=diagnosis.fault_type,
            alarm_code=diagnosis.alarm_code,
            fault_description=diagnosis.fault_description,
            diagnosis_summary=summary,
            possible_causes=diagnosis.possible_causes or [],
            inspection_steps=diagnosis.inspection_steps or [],
            recommended_actions=diagnosis.recommended_actions or [],
            safety_notes=diagnosis.safety_notes or [],
            references=diagnosis.references or [],
            related_history=diagnosis.related_history or [],
            media_ids=[str(item) for item in diagnosis.media_ids or []],
            is_recurrent=bool(diagnosis.related_history),
            recurrent_reference_record_id=None,
            confidence=diagnosis.confidence,
            model_provider=diagnosis.model_provider,
            model_name=diagnosis.model_name,
            created_by=diagnosis.created_by,
            created_at=diagnosis.created_at,
            updated_at=diagnosis.updated_at,
        ).model_dump(mode="json")

    def _resolve_device(self, device_id: UUID | None) -> Device | None:
        if not device_id:
            return None
        device = self.repository.get_device(device_id)
        if not device:
            raise MaintenanceTaskServiceError("Device not found")
        if device.device_type != "pv_inverter":
            raise MaintenanceTaskServiceError("device_type must be pv_inverter")
        return device

    def _resolve_diagnosis(self, trace_id: str | None) -> DiagnosisRecord | None:
        if not trace_id:
            return None
        diagnosis = self.repository.get_diagnosis_by_trace_id(trace_id)
        if not diagnosis:
            raise MaintenanceTaskServiceError("Diagnosis record not found")
        return diagnosis

    def _resolve_sop_template(self, template_id: UUID | None, *, allow_archived: bool = False) -> SOPTemplate | None:
        if not template_id:
            return None
        template = self.repository.get_sop_template(template_id)
        if not template:
            raise MaintenanceTaskServiceError("SOP template not found")
        if template.status == "archived" and not allow_archived:
            raise MaintenanceTaskServiceError("Archived SOP template cannot be linked")
        return template

    def _resolve_sop_execution(self, execution_id: UUID | None) -> SOPExecutionRecord | None:
        if not execution_id:
            return None
        execution = self.repository.get_sop_execution(execution_id)
        if not execution:
            raise MaintenanceTaskServiceError("SOP execution record not found")
        return execution

    def _resolve_assignee(self, assignee_id: UUID | None) -> User | None:
        if not assignee_id:
            return None
        user = self.repository.get_user(assignee_id)
        if not user:
            raise MaintenanceTaskServiceError("Assignee not found")
        if user.role not in TaskWorkflowService.ASSIGNABLE_ROLES:
            raise MaintenanceTaskServiceError("Assignee role must be admin, expert, or engineer")
        if user.status != "active" or not user.is_active:
            raise MaintenanceTaskServiceError("Assignee is not active")
        return user

    def _get_task_or_error(self, task_id: UUID) -> MaintenanceTask:
        task = self.repository.get_by_id(task_id)
        if not task:
            raise MaintenanceTaskServiceError("Maintenance task not found")
        return task

    @staticmethod
    def _default_title(device: Device | None, fault_type: str | None, alarm_code: str | None) -> str:
        device_name = device.device_name if device else "PV inverter"
        fault = fault_type or alarm_code or "maintenance"
        return f"{device_name} {fault} task"

    @staticmethod
    def _user_name(user: User | None) -> str | None:
        if not user:
            return None
        return user.display_name or user.username

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise MaintenanceTaskServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise MaintenanceTaskServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in TASK_STATUSES:
            raise MaintenanceTaskServiceError("unsupported task status")

    @staticmethod
    def _validate_priority(priority: str) -> None:
        if priority not in TASK_PRIORITIES:
            raise MaintenanceTaskServiceError("unsupported task priority")
