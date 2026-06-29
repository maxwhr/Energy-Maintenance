from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Device, DiagnosisRecord, MaintenanceTask, SOPTemplate, User
from app.schemas.maintenance_task import MaintenanceTaskCreateRequest
from app.services.maintenance_task_service import MaintenanceTaskService


DEMO_TASKS = [
    {
        "device_code": "HW-SUN2000-100KTL-M2-002",
        "title": "Huawei SUN2000 low insulation maintenance task",
        "fault_type": "low_insulation",
        "alarm_code": "INSULATION_LOW",
        "priority": "high",
    },
    {
        "device_code": "HW-SUN2000-50KTL-M3-001",
        "title": "Huawei FusionSolar communication interruption task",
        "fault_type": "communication_fault",
        "alarm_code": "COM_LOST",
        "priority": "medium",
    },
    {
        "device_code": "SG-SG50CX-003",
        "title": "Sungrow SG overtemperature maintenance task",
        "fault_type": "overtemperature",
        "alarm_code": "TEMP_HIGH",
        "priority": "urgent",
    },
    {
        "device_code": "SG-SG110CX-004",
        "title": "Sungrow SG MPPT low power inspection task",
        "fault_type": "mppt_low_power",
        "alarm_code": "MPPT_LOW_POWER",
        "priority": "medium",
    },
]


def ensure_engineer(db) -> User:
    user = db.scalar(select(User).where(User.username == "engineer_task10"))
    if user:
        return user
    user = User(
        username="engineer_task10",
        password_hash=hash_password("engineer123456"),
        display_name="Task10 Engineer",
        role="engineer",
        status="active",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def find_diagnosis(db, device: Device, fault_type: str) -> DiagnosisRecord | None:
    return db.scalar(
        select(DiagnosisRecord)
        .where(DiagnosisRecord.device_id == device.id, DiagnosisRecord.fault_type == fault_type)
        .order_by(DiagnosisRecord.created_at.desc())
    )


def find_template(db, device: Device, fault_type: str) -> SOPTemplate | None:
    return db.scalar(
        select(SOPTemplate)
        .where(
            SOPTemplate.status == "active",
            SOPTemplate.device_type == "pv_inverter",
            SOPTemplate.manufacturer == device.manufacturer,
            SOPTemplate.product_series == device.product_series,
            SOPTemplate.fault_type == fault_type,
        )
        .order_by(SOPTemplate.version.desc(), SOPTemplate.updated_at.desc())
    )


def main() -> int:
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        admin = db.scalar(select(User).where(User.username == "admin"))
        if not admin:
            print("Admin user not found. Run scripts/create_admin_user.py first.")
            return 1
        engineer = ensure_engineer(db)
        service = MaintenanceTaskService(db)
        for item in DEMO_TASKS:
            device = db.scalar(select(Device).where(Device.device_code == item["device_code"]))
            if not device:
                print(f"skip missing device: {item['device_code']}")
                skipped += 1
                continue
            duplicate = db.scalar(
                select(MaintenanceTask).where(
                    MaintenanceTask.device_id == device.id,
                    MaintenanceTask.title == item["title"],
                    MaintenanceTask.fault_type == item["fault_type"],
                )
            )
            if duplicate:
                print(f"skip task: {item['title']}")
                skipped += 1
                continue
            diagnosis = find_diagnosis(db, device, item["fault_type"])
            template = find_template(db, device, item["fault_type"])
            service.create_task(
                MaintenanceTaskCreateRequest(
                    device_id=device.id,
                    diagnosis_trace_id=diagnosis.trace_id if diagnosis else None,
                    sop_template_id=template.id if template else None,
                    title=item["title"],
                    fault_type=item["fault_type"],
                    alarm_code=item["alarm_code"],
                    priority=item["priority"],
                    assignee_id=engineer.id,
                    remark="Seeded by Task10 demo task script.",
                ),
                admin,
            )
            print(f"insert task: {item['title']}")
            created += 1
        print(f"demo_task_seed_result created={created} skipped={skipped}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
