from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.repositories.device_history_repository import DeviceHistoryRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.device import DeviceCreate, DeviceMaintenanceRecordCreate
from app.services.device_history_service import DeviceHistoryService
from app.services.device_service import DeviceService


DEMO_DEVICES = [
    {
        "device_code": "HW-SUN2000-50KTL-M3-001",
        "device_name": "Huawei SUN2000-50KTL-M3 Inverter 001",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-50KTL-M3",
        "status": "normal",
        "station_name": "PV Station A",
        "location": "Inverter Room A1",
    },
    {
        "device_code": "HW-SUN2000-100KTL-M2-002",
        "device_name": "Huawei SUN2000-100KTL-M2 Inverter 002",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-100KTL-M2",
        "status": "fault",
        "station_name": "PV Station A",
        "location": "Outdoor Area A2",
    },
    {
        "device_code": "SG-SG50CX-003",
        "device_name": "Sungrow SG50CX Inverter 003",
        "manufacturer": "sungrow",
        "product_series": "SG",
        "model": "SG50CX",
        "status": "maintenance",
        "station_name": "PV Station B",
        "location": "Inverter Room B1",
    },
    {
        "device_code": "SG-SG110CX-004",
        "device_name": "Sungrow SG110CX Inverter 004",
        "manufacturer": "sungrow",
        "product_series": "SG",
        "model": "SG110CX",
        "status": "offline",
        "station_name": "PV Station B",
        "location": "Outdoor Area B2",
    },
]

DEMO_RECORDS = {
    "HW-SUN2000-100KTL-M2-002": {
        "fault_type": "low_insulation",
        "alarm_code": "INSULATION_LOW",
        "fault_description": "Insulation resistance alarm appeared during morning startup.",
        "root_cause": "DC cable connector moisture was found during inspection.",
        "repair_action": "Powered down according to safety procedure, dried connector, and tightened waterproof seal.",
        "verification_result": "Insulation resistance returned to normal range after retest.",
    },
    "SG-SG50CX-003": {
        "fault_type": "overtemperature",
        "alarm_code": "TEMP_HIGH",
        "fault_description": "Inverter derated due to cabinet temperature warning.",
        "root_cause": "Air inlet filter was blocked by dust.",
        "repair_action": "Cleaned inlet filter and checked fan operation.",
        "verification_result": "Temperature trend returned to normal after load recovery.",
    },
    "SG-SG110CX-004": {
        "fault_type": "communication_fault",
        "alarm_code": "COM_LOST",
        "fault_description": "Monitoring platform reported communication interruption.",
        "root_cause": "Communication cable terminal was loose.",
        "repair_action": "Reconnected terminal and verified data upload.",
        "verification_result": "Device telemetry recovered on FusionSolar-compatible monitoring interface.",
    },
}


def main() -> int:
    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_username("admin")
        if not user:
            print("Admin user not found. Run scripts/create_admin_user.py first.")
            return 1

        device_repository = DeviceRepository(db)
        device_service = DeviceService(db)
        history_repository = DeviceHistoryRepository(db)
        history_service = DeviceHistoryService(db)

        for item in DEMO_DEVICES:
            existing = device_repository.get_by_code(item["device_code"])
            if existing:
                print(f"skip device: {item['device_code']}")
                continue
            device_service.create_device(DeviceCreate(**item))
            print(f"insert device: {item['device_code']}")

        for device_code, record_data in DEMO_RECORDS.items():
            device = device_repository.get_by_code(device_code)
            if not device:
                print(f"skip record, device missing: {device_code}")
                continue
            records, total = history_repository.list_by_device(
                device_id=device.id,
                fault_type=record_data["fault_type"],
                alarm_code=record_data["alarm_code"],
                page=1,
                page_size=1,
            )
            if total > 0:
                print(f"skip maintenance record: {device_code} {record_data['fault_type']}")
                continue
            history_service.create_record(
                device_id=device.id,
                payload=DeviceMaintenanceRecordCreate(
                    **record_data,
                    completed_at=datetime.now(timezone.utc) - timedelta(days=3),
                ),
                current_user=user,
            )
            print(f"insert maintenance record: {device_code} {record_data['fault_type']}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
