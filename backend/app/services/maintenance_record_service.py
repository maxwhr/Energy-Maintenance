from __future__ import annotations

from datetime import datetime, timezone

from app.models import Device, DeviceMaintenanceRecord, MaintenanceTask, User
from app.repositories.maintenance_record_repository import MaintenanceRecordRepository
from app.schemas.maintenance_task import MaintenanceTaskCompleteRequest


class MaintenanceRecordServiceError(ValueError):
    pass


class MaintenanceRecordService:
    def __init__(self, repository: MaintenanceRecordRepository):
        self.repository = repository

    def ensure_record_from_task(
        self,
        *,
        task: MaintenanceTask,
        device: Device | None,
        payload: MaintenanceTaskCompleteRequest,
        current_user: User,
    ) -> DeviceMaintenanceRecord:
        if not device:
            raise MaintenanceRecordServiceError("Task must be linked to a device before completion")
        existing = self.repository.get_by_task_id(task.id)
        if existing:
            raise MaintenanceRecordServiceError("Maintenance record already exists for this task")

        completed_at = payload.completed_at or datetime.now(timezone.utc)
        source_trace = task.source_trace_id
        diagnosis_trace_id = source_trace if task.source_type == "diagnosis" else None
        qa_trace_id = source_trace if task.source_type == "qa" else None
        record = DeviceMaintenanceRecord(
            device_id=device.id,
            task_id=task.id,
            diagnosis_trace_id=diagnosis_trace_id,
            qa_trace_id=qa_trace_id,
            fault_type=task.fault_type,
            alarm_code=task.alarm_code,
            fault_description=task.fault_description,
            root_cause=payload.root_cause,
            repair_action=payload.repair_action,
            replaced_parts=", ".join(payload.replaced_parts),
            verification_result=payload.verification_result,
            is_recurrent=payload.is_recurrent,
            recurrent_reference_record_id=payload.recurrent_reference_record_id,
            completed_by=current_user.id,
            completed_at=completed_at,
            attachments=[],
            metadata_json={
                "source": "maintenance_task",
                "maintenance_record_remark": payload.maintenance_record_remark,
                "sop_template_id": str(task.sop_template_id) if task.sop_template_id else None,
                "sop_execution_id": str(task.sop_execution_id) if task.sop_execution_id else None,
            },
        )
        record = self.repository.create(record)

        device.last_maintenance_at = completed_at
        device.maintenance_count = (device.maintenance_count or 0) + 1
        if task.fault_type or task.alarm_code:
            device.last_fault_at = completed_at
            device.fault_count = (device.fault_count or 0) + 1
        return record
