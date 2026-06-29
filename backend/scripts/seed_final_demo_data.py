from __future__ import annotations

import base64
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import or_, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KnowledgeChunk,
    KnowledgeContribution,
    KnowledgeDocument,
    KnowledgeReviewRecord,
    MaintenanceTask,
    ModelOutputCorrection,
    QARecord,
    SOPTemplate,
    UploadedMedia,
    User,
)


DEMO_SOURCE = "final_demo_seed"
DEMO_PASSWORD = "admin123456"


def ensure_user(db, username: str, role: str, display_name: str) -> User:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user:
        user.role = role
        user.display_name = display_name
        user.status = "active"
        user.is_active = True
        if not user.password_hash:
            user.password_hash = hash_password(DEMO_PASSWORD)
        return user
    user = User(
        username=username,
        password_hash=hash_password(DEMO_PASSWORD),
        display_name=display_name,
        role=role,
        status="active",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def ensure_device(db, code: str, **values) -> Device:
    device = db.execute(select(Device).where(Device.device_code == code)).scalar_one_or_none()
    if not device:
        device = Device(device_code=code, **values)
        db.add(device)
    else:
        for key, value in values.items():
            setattr(device, key, value)
    db.flush()
    return device


def ensure_document(db, title: str, chunks: list[dict], **values) -> KnowledgeDocument:
    document = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.title == title,
            or_(
                KnowledgeDocument.source == DEMO_SOURCE,
                KnowledgeDocument.metadata_json["seed_source"].astext == DEMO_SOURCE,
            ),
        )
    ).scalar_one_or_none()
    if not document:
        document = KnowledgeDocument(title=title, source=DEMO_SOURCE, **values)
        db.add(document)
        db.flush()
    else:
        for key, value in values.items():
            setattr(document, key, value)

    existing_chunks = db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document.id)
        .order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.created_at.asc())
    ).scalars().all()
    existing_by_index = {chunk.chunk_index: chunk for chunk in existing_chunks}
    used_chunk_ids = set()
    for index, chunk in enumerate(chunks):
        existing = existing_by_index.get(index)
        if not existing:
            existing = KnowledgeChunk(document_id=document.id, chunk_index=index)
            db.add(existing)
        existing.manufacturer = document.manufacturer
        existing.product_series = document.product_series
        existing.device_type = document.device_type
        existing.document_type = document.document_type
        existing.content = chunk["content"]
        existing.section_title = chunk.get("section_title")
        existing.char_count = len(chunk["content"])
        existing.page_number = chunk.get("page_number")
        existing.embedding_status = "pending"
        existing.metadata_json = {"seed_source": DEMO_SOURCE}
        existing.status = "active"
        if existing.id:
            used_chunk_ids.add(existing.id)

    for chunk in existing_chunks:
        if chunk.id not in used_chunk_ids:
            chunk.status = "archived"
            chunk.embedding_status = "pending"
    document.chunk_count = len(chunks)
    document.parse_status = "parsed"
    document.review_status = "approved"
    document.error_message = None
    document.parsed_at = datetime.now(timezone.utc)
    document.metadata_json = {"seed_source": DEMO_SOURCE, "repeatable": True}
    db.flush()
    return document


def ensure_trace_record(db, record_model, trace_id: str, **values):
    record = db.execute(select(record_model).where(record_model.trace_id == trace_id)).scalar_one_or_none()
    if not record:
        record = record_model(trace_id=trace_id, **values)
        db.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
    db.flush()
    return record


def ensure_sop_template(db, title: str, **values) -> SOPTemplate:
    template = db.execute(select(SOPTemplate).where(SOPTemplate.title == title)).scalar_one_or_none()
    if not template:
        template = SOPTemplate(title=title, **values)
        db.add(template)
    else:
        for key, value in values.items():
            setattr(template, key, value)
    db.flush()
    return template


def ensure_maintenance_record(db, diagnosis_trace_id: str, **values) -> DeviceMaintenanceRecord:
    record = db.execute(
        select(DeviceMaintenanceRecord).where(DeviceMaintenanceRecord.diagnosis_trace_id == diagnosis_trace_id)
    ).scalar_one_or_none()
    if not record:
        record = DeviceMaintenanceRecord(diagnosis_trace_id=diagnosis_trace_id, **values)
        db.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
    db.flush()
    return record


def ensure_contribution(db, title: str, **values) -> KnowledgeContribution:
    contribution = db.execute(
        select(KnowledgeContribution).where(KnowledgeContribution.title == title, KnowledgeContribution.source_type == DEMO_SOURCE)
    ).scalar_one_or_none()
    if not contribution:
        contribution = KnowledgeContribution(title=title, source_type=DEMO_SOURCE, **values)
        db.add(contribution)
    else:
        for key, value in values.items():
            setattr(contribution, key, value)
    db.flush()
    return contribution


def ensure_review_record(db, contribution: KnowledgeContribution, action: str, **values) -> KnowledgeReviewRecord:
    record = db.execute(
        select(KnowledgeReviewRecord).where(
            KnowledgeReviewRecord.contribution_id == contribution.id,
            KnowledgeReviewRecord.review_action == action,
            KnowledgeReviewRecord.metadata_json["seed_source"].astext == DEMO_SOURCE,
        )
    ).scalar_one_or_none()
    if not record:
        record = KnowledgeReviewRecord(
            contribution_id=contribution.id,
            review_action=action,
            metadata_json={"seed_source": DEMO_SOURCE},
            **values,
        )
        db.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
        metadata = dict(record.metadata_json or {})
        metadata["seed_source"] = DEMO_SOURCE
        record.metadata_json = metadata
    db.flush()
    return record


def ensure_correction(db, source_trace_id: str, **values) -> ModelOutputCorrection:
    correction = db.execute(
        select(ModelOutputCorrection).where(ModelOutputCorrection.source_trace_id == source_trace_id)
    ).scalar_one_or_none()
    if not correction:
        correction = ModelOutputCorrection(source_trace_id=source_trace_id, **values)
        db.add(correction)
    else:
        for key, value in values.items():
            setattr(correction, key, value)
    db.flush()
    return correction


def ensure_task(db, title: str, **values) -> MaintenanceTask:
    task = db.execute(select(MaintenanceTask).where(MaintenanceTask.title == title)).scalar_one_or_none()
    if not task:
        task = MaintenanceTask(title=title, **values)
        db.add(task)
    else:
        for key, value in values.items():
            setattr(task, key, value)
    db.flush()
    return task


def ensure_media(db, file_name: str, file_bytes: bytes, **values) -> UploadedMedia:
    media_dir = ROOT_DIR / "storage" / "uploads" / "media" / "final_demo"
    media_dir.mkdir(parents=True, exist_ok=True)
    file_path = media_dir / file_name
    if not file_path.exists() or file_path.read_bytes() != file_bytes:
        file_path.write_bytes(file_bytes)

    media = db.execute(
        select(UploadedMedia).where(
            UploadedMedia.file_name == file_name,
            UploadedMedia.metadata_json["seed_source"].astext == DEMO_SOURCE,
        )
    ).scalar_one_or_none()
    if not media:
        media = UploadedMedia(file_name=file_name, file_path=str(file_path.relative_to(ROOT_DIR)), **values)
        db.add(media)
    else:
        media.file_path = str(file_path.relative_to(ROOT_DIR))
        for key, value in values.items():
            setattr(media, key, value)
    db.flush()
    return media


def main() -> int:
    db = SessionLocal()
    try:
        admin = ensure_user(db, "admin", "admin", "System Administrator")
        ensure_user(db, "expert", "expert", "Maintenance Expert")
        ensure_user(db, "engineer", "engineer", "Field Engineer")
        ensure_user(db, "viewer", "viewer", "Read Only Viewer")

        huawei_device = ensure_device(
            db,
            "EM-DEMO-HW-SUN2000-01",
            device_name="Huawei SUN2000 Demo Inverter",
            manufacturer="huawei",
            product_series="SUN2000",
            model="SUN2000-50KTL-M3",
            device_type="pv_inverter",
            station_name="Demo PV Station A",
            location="Inverter room A-01",
            status="normal",
            description="Repeatable final demo device for Huawei SUN2000 maintenance workflow.",
        )
        fusion_device = ensure_device(
            db,
            "EM-DEMO-HW-FUSIONSOLAR-01",
            device_name="Huawei FusionSolar Demo Inverter",
            manufacturer="huawei",
            product_series="FusionSolar",
            model="SUN2000-100KTL-M2",
            device_type="pv_inverter",
            station_name="Demo PV Station A",
            location="Inverter room A-02",
            status="maintenance",
            description="Repeatable final demo device for FusionSolar communication workflow.",
        )
        sungrow_device = ensure_device(
            db,
            "EM-DEMO-SG-01",
            device_name="Sungrow SG Demo Inverter",
            manufacturer="sungrow",
            product_series="SG",
            model="SG110CX",
            device_type="pv_inverter",
            station_name="Demo PV Station B",
            location="Inverter room B-02",
            status="normal",
            description="Repeatable final demo device for Sungrow SG maintenance workflow.",
        )
        sungrow_mppt_device = ensure_device(
            db,
            "EM-DEMO-SG-MPPT-01",
            device_name="Sungrow SG MPPT Demo Inverter",
            manufacturer="sungrow",
            product_series="SG",
            model="SG125HX",
            device_type="pv_inverter",
            station_name="Demo PV Station C",
            location="Inverter room C-03",
            status="fault",
            description="Repeatable final demo device for MPPT low generation workflow.",
        )

        huawei_doc = ensure_document(
            db,
            "Final Demo Huawei SUN2000 Insulation Alarm Manual",
            [
                {
                    "section_title": "Low insulation resistance alarm",
                    "content": (
                        "For Huawei SUN2000 PV inverter low insulation resistance alarms, stop remote reset attempts, "
                        "verify DC switch state, measure PV string insulation resistance, inspect connectors after rain, "
                        "and record alarm code, string number, weather condition, and measured insulation value."
                    ),
                    "page_number": 1,
                },
                {
                    "section_title": "Safety and recovery",
                    "content": (
                        "Before opening the DC side, confirm isolation, wear electrical PPE, wait for capacitor discharge, "
                        "and follow the manufacturer maintenance manual. Restore operation only after abnormal strings or "
                        "damaged connectors are isolated and the insulation value is acceptable."
                    ),
                    "page_number": 2,
                },
            ],
            manufacturer="huawei",
            product_series="SUN2000",
            model="SUN2000-50KTL-M3",
            device_type="pv_inverter",
            document_type="manual",
            source_type="seed",
            file_name="final_demo_huawei_sun2000_insulation.txt",
            file_ext="txt",
            file_size=1024,
            page_count=2,
            parser_name="seed",
            summary="Final demo knowledge source for Huawei SUN2000 insulation alarm troubleshooting.",
            status="active",
            submitted_by=admin.id,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        sungrow_doc = ensure_document(
            db,
            "Final Demo Sungrow SG Communication Alarm SOP",
            [
                {
                    "section_title": "Communication interruption check",
                    "content": (
                        "For Sungrow SG inverter communication interruption, confirm AC and auxiliary power, inspect RS485 "
                        "or Ethernet wiring, verify logger address settings, check monitoring platform status, and compare "
                        "local inverter alarm information with station communication gateway logs."
                    ),
                    "page_number": 1,
                },
                {
                    "section_title": "On-site confirmation",
                    "content": (
                        "If the device is generating normally but offline on the monitoring platform, prioritize network, "
                        "logger, address conflict, and gateway configuration checks before replacing inverter hardware."
                    ),
                    "page_number": 2,
                },
            ],
            manufacturer="sungrow",
            product_series="SG",
            model="SG110CX",
            device_type="pv_inverter",
            document_type="sop",
            source_type="seed",
            file_name="final_demo_sungrow_sg_communication.txt",
            file_ext="txt",
            file_size=1024,
            page_count=2,
            parser_name="seed",
            summary="Final demo knowledge source for Sungrow SG communication alarm handling.",
            status="active",
            submitted_by=admin.id,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        fusion_doc = ensure_document(
            db,
            "Final Demo Huawei FusionSolar Communication Case",
            [
                {
                    "section_title": "FusionSolar communication abnormality",
                    "content": (
                        "When FusionSolar shows communication abnormality for a Huawei PV inverter, compare local device "
                        "status with platform status, verify the logger, plant network, device address, and monitoring "
                        "gateway routing. If generation is normal, avoid unnecessary inverter replacement."
                    ),
                    "page_number": 1,
                },
                {
                    "section_title": "Communication recovery record",
                    "content": (
                        "Record alarm time, platform recovery time, logger address, network test result, and whether the "
                        "device was locally normal during the communication interruption."
                    ),
                    "page_number": 2,
                },
            ],
            manufacturer="huawei",
            product_series="FusionSolar",
            model="SUN2000-100KTL-M2",
            device_type="pv_inverter",
            document_type="fault_case",
            source_type="seed",
            file_name="final_demo_huawei_fusionsolar_communication.txt",
            file_ext="txt",
            file_size=1024,
            page_count=2,
            parser_name="seed",
            summary="Final demo case for Huawei FusionSolar communication abnormality troubleshooting.",
            status="active",
            submitted_by=admin.id,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        sungrow_overtemp_doc = ensure_document(
            db,
            "Final Demo Sungrow SG Over Temperature Case",
            [
                {
                    "section_title": "Over temperature alarm",
                    "content": (
                        "For Sungrow SG inverter over temperature alarms, check ambient temperature, ventilation path, "
                        "fan operation, heat sink blockage, derating records, and whether alarms occur under high load "
                        "at noon."
                    ),
                    "page_number": 1,
                },
                {
                    "section_title": "Thermal recovery",
                    "content": (
                        "Clean air inlets, verify fan rotation, restore cabinet ventilation, and monitor temperature trend "
                        "after recovery before closing the work order."
                    ),
                    "page_number": 2,
                },
            ],
            manufacturer="sungrow",
            product_series="SG",
            model="SG110CX",
            device_type="pv_inverter",
            document_type="fault_case",
            source_type="seed",
            file_name="final_demo_sungrow_sg_over_temperature.txt",
            file_ext="txt",
            file_size=1024,
            page_count=2,
            parser_name="seed",
            summary="Final demo case for Sungrow SG over temperature handling.",
            status="active",
            submitted_by=admin.id,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        sungrow_mppt_doc = ensure_document(
            db,
            "Final Demo Sungrow SG MPPT Low Generation Case",
            [
                {
                    "section_title": "MPPT low generation",
                    "content": (
                        "For Sungrow SG MPPT low generation, compare string current, DC voltage, irradiance, shading, "
                        "connector condition, and historical generation curve. Check whether one MPPT input is abnormal "
                        "while other inputs remain normal."
                    ),
                    "page_number": 1,
                },
                {
                    "section_title": "String side inspection",
                    "content": (
                        "Inspect PV string polarity, connector heating, fuse status, combiner wiring, and module shading. "
                        "Record current comparison before and after correction."
                    ),
                    "page_number": 2,
                },
            ],
            manufacturer="sungrow",
            product_series="SG",
            model="SG125HX",
            device_type="pv_inverter",
            document_type="fault_case",
            source_type="seed",
            file_name="final_demo_sungrow_sg_mppt_low_generation.txt",
            file_ext="txt",
            file_size=1024,
            page_count=2,
            parser_name="seed",
            summary="Final demo case for Sungrow SG MPPT low generation troubleshooting.",
            status="active",
            submitted_by=admin.id,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )

        ensure_trace_record(
            db,
            QARecord,
            "FINAL-DEMO-QA-LOW-INSULATION",
            question="How should a Huawei SUN2000 low insulation resistance alarm be checked?",
            normalized_query="huawei sun2000 low insulation resistance alarm check",
            manufacturer="huawei",
            product_series="SUN2000",
            device_type="pv_inverter",
            document_type="manual",
            answer="Check DC isolation, PV string insulation resistance, connector condition, alarm code, and recovery records.",
            references=[
                {
                    "document_id": str(huawei_doc.id),
                    "document_title": huawei_doc.title,
                    "chunk_index": 0,
                    "section_title": "Low insulation resistance alarm",
                    "source": DEMO_SOURCE,
                    "score": 0.82,
                }
            ],
            retrieved_chunks=[],
            suggested_steps=["Safety isolation", "Alarm code confirmation", "PV string insulation measurement", "Connector inspection", "Recovery record"],
            safety_notes=["Follow manufacturer electrical isolation and PPE requirements."],
            related_history=[],
            confidence=0.78,
            created_by=admin.id,
        )
        ensure_trace_record(
            db,
            QARecord,
            "FINAL-DEMO-QA-FUSIONSOLAR-COMM",
            question="What should be checked when FusionSolar shows a Huawei inverter communication abnormality?",
            normalized_query="huawei fusionsolar communication abnormality check",
            manufacturer="huawei",
            product_series="FusionSolar",
            device_id=fusion_device.id,
            device_type="pv_inverter",
            document_type="fault_case",
            answer="Compare local inverter status with FusionSolar, then inspect logger, address, gateway, and plant network.",
            references=[
                {
                    "document_id": str(fusion_doc.id),
                    "document_title": fusion_doc.title,
                    "chunk_index": 0,
                    "section_title": "FusionSolar communication abnormality",
                    "source": DEMO_SOURCE,
                    "score": 0.81,
                }
            ],
            retrieved_chunks=[],
            suggested_steps=["Check local status", "Inspect logger", "Verify address", "Check network gateway", "Record recovery"],
            safety_notes=["Do not replace inverter hardware before communication-side checks are complete."],
            related_history=[],
            confidence=0.77,
            created_by=admin.id,
        )
        diag_record = ensure_trace_record(
            db,
            DiagnosisRecord,
            "FINAL-DEMO-DIAG-SG-COMM",
            manufacturer="sungrow",
            product_series="SG",
            device_id=sungrow_device.id,
            device_type="pv_inverter",
            device_name=sungrow_device.device_name,
            model=sungrow_device.model,
            fault_type="communication_interruption",
            alarm_code="COMM-001",
            alarm_info="Communication interruption",
            fault_description="Monitoring platform shows the Sungrow SG inverter offline while local generation is normal.",
            possible_causes=["Gateway network abnormality", "RS485 or Ethernet wiring fault", "Logger address conflict"],
            inspection_steps=["Check local inverter status", "Inspect communication wiring", "Verify gateway and address configuration"],
            safety_notes=["Confirm electrical safety before opening communication cabinets."],
            recommended_actions=["Restore network link", "Correct logger address settings", "Record platform recovery time"],
            references=[
                {
                    "document_id": str(sungrow_doc.id),
                    "document_title": sungrow_doc.title,
                    "chunk_index": 0,
                    "section_title": "Communication interruption check",
                    "source": DEMO_SOURCE,
                    "score": 0.8,
                }
            ],
            related_history=[],
            media_ids=[],
            confidence=0.76,
            created_by=admin.id,
        )
        demo_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lx9G7wAAAABJRU5ErkJggg=="
        )
        demo_media = ensure_media(
            db,
            "final_demo_sungrow_sg_comm_evidence.png",
            demo_png,
            original_file_name="final_demo_sungrow_sg_comm_evidence.png",
            file_ext="png",
            mime_type="image/png",
            file_size=len(demo_png),
            media_type="image",
            description="Final demo media evidence for Sungrow SG communication troubleshooting.",
            ocr_text=None,
            manufacturer="sungrow",
            product_series="SG",
            device_type="pv_inverter",
            device_id=sungrow_device.id,
            diagnosis_record_id=diag_record.id,
            qa_trace_id="FINAL-DEMO-QA-FUSIONSOLAR-COMM",
            uploaded_by=admin.id,
            status="uploaded",
            metadata_json={"seed_source": DEMO_SOURCE, "repeatable": True},
        )
        diag_record.media_ids = [str(demo_media.id)]

        sop = ensure_sop_template(
            db,
            "Final Demo PV Inverter Alarm Handling SOP",
            manufacturer="huawei",
            product_series="SUN2000",
            device_type="pv_inverter",
            fault_type="low_insulation_resistance",
            maintenance_level="level_2",
            steps=[
                {"index": 1, "title": "Safety isolation", "description": "Confirm DC/AC isolation and PPE."},
                {"index": 2, "title": "Alarm confirmation", "description": "Record alarm code and affected string."},
                {"index": 3, "title": "Insulation test", "description": "Measure string insulation resistance."},
            ],
            safety_requirements=[{"item": "Electrical PPE"}, {"item": "Capacitor discharge waiting time"}],
            tools_required=[{"item": "Insulation resistance tester"}, {"item": "Multimeter"}],
            materials_required=[{"item": "Replacement connector kit"}],
            compliance_notes="Demo SOP for Huawei/Sungrow PV inverter final delivery verification.",
            status="active",
            version=1,
            created_by=admin.id,
            updated_by=admin.id,
            metadata_json={"seed_source": DEMO_SOURCE},
        )
        overtemp_sop = ensure_sop_template(
            db,
            "Final Demo Sungrow SG Over Temperature SOP",
            manufacturer="sungrow",
            product_series="SG",
            device_type="pv_inverter",
            fault_type="over_temperature",
            maintenance_level="level_2",
            steps=[
                {"index": 1, "title": "Confirm alarm", "description": "Record temperature alarm and load condition."},
                {"index": 2, "title": "Ventilation check", "description": "Inspect fans, inlets, heat sink, and cabinet ventilation."},
                {"index": 3, "title": "Recovery monitor", "description": "Monitor temperature trend after cleaning or fan recovery."},
            ],
            safety_requirements=[{"item": "Avoid touching hot components"}, {"item": "Follow electrical isolation rules"}],
            tools_required=[{"item": "Thermal imager"}, {"item": "Multimeter"}],
            materials_required=[{"item": "Filter mesh"}, {"item": "Fan module if confirmed faulty"}],
            compliance_notes="Demo SOP for Sungrow SG over temperature alarm.",
            status="active",
            version=1,
            created_by=admin.id,
            updated_by=admin.id,
            metadata_json={"seed_source": DEMO_SOURCE},
        )
        ensure_task(
            db,
            "Final Demo Huawei SUN2000 insulation alarm verification",
            manufacturer="huawei",
            product_series="SUN2000",
            device_type="pv_inverter",
            device_id=huawei_device.id,
            device_name=huawei_device.device_name,
            model=huawei_device.model,
            fault_type="low_insulation_resistance",
            alarm_code="LOW-INS",
            fault_description="Final demo task for low insulation resistance alarm troubleshooting.",
            priority="high",
            task_status="pending",
            status="pending",
            assignee="Field Engineer",
            source_type="seed",
            source_trace_id="FINAL-DEMO-QA-LOW-INSULATION",
            sop_template_id=sop.id,
            suggested_steps=["Safety isolation", "PV string insulation measurement", "Connector inspection"],
            created_by=admin.id,
        )
        ensure_task(
            db,
            "Final Demo Sungrow SG over temperature in-progress task",
            manufacturer="sungrow",
            product_series="SG",
            device_type="pv_inverter",
            device_id=sungrow_device.id,
            device_name=sungrow_device.device_name,
            model=sungrow_device.model,
            fault_type="over_temperature",
            alarm_code="TEMP-HIGH",
            fault_description="Final demo in-progress task for Sungrow SG over temperature alarm.",
            priority="medium",
            task_status="in_progress",
            status="in_progress",
            assignee="Field Engineer",
            source_type="seed",
            source_trace_id="FINAL-DEMO-DIAG-SG-COMM",
            sop_template_id=overtemp_sop.id,
            suggested_steps=["Confirm alarm", "Check ventilation", "Inspect fan", "Monitor recovery"],
            created_by=admin.id,
        )
        ensure_maintenance_record(
            db,
            "FINAL-DEMO-DIAG-SG-COMM",
            device_id=sungrow_device.id,
            task_id=None,
            qa_trace_id="FINAL-DEMO-QA-FUSIONSOLAR-COMM",
            fault_type="communication_interruption",
            alarm_code="COMM-001",
            fault_description="FusionSolar/platform offline alarm was compared with local device status.",
            root_cause="Communication gateway address conflict.",
            repair_action="Corrected logger address and verified platform recovery.",
            replaced_parts=None,
            verification_result="Platform status recovered and local generation remained normal.",
            is_recurrent=False,
            completed_by=admin.id,
            completed_at=datetime.now(timezone.utc),
            attachments=[],
            metadata_json={"seed_source": DEMO_SOURCE},
        )
        converted_contribution = ensure_contribution(
            db,
            "Final Demo Converted Huawei SUN2000 Field Contribution",
            content=(
                "# SUN2000 低绝缘阻抗现场经验\n\n"
                "## 故障现象\n"
                "Huawei SUN2000 inverter reported low insulation resistance after rain. The affected PV string showed unstable insulation values.\n\n"
                "## 处理过程\n"
                "The field engineer isolated DC switches, measured each PV string, inspected wet connectors, and compared the alarm timestamp with weather records.\n\n"
                "## 原因判断\n"
                "Connector moisture and string insulation degradation were considered the primary causes before inverter hardware replacement.\n\n"
                "## 处理措施\n"
                "Dry and replace abnormal connectors, retest insulation resistance, restore operation after values are acceptable, and archive the measurement record.\n\n"
                "## 安全注意事项\n"
                "- Confirm DC and AC isolation before opening combiner or inverter terminals.\n"
                "- Wear electrical PPE and follow manufacturer maintenance manual requirements."
            ),
            contribution_type="maintenance_experience",
            manufacturer="huawei",
            product_series="SUN2000",
            device_type="pv_inverter",
            device_id=huawei_device.id,
            source_trace_id="FINAL-DEMO-QA-LOW-INSULATION",
            submitted_by=admin.id,
            review_status="converted",
            review_comment="Approved and converted for final demo.",
            metadata_json={
                "seed_source": DEMO_SOURCE,
                "fault_type": "low_insulation_resistance",
                "alarm_code": "LOW-INS",
                "symptom_description": "Low insulation resistance alarm after rain.",
                "diagnosis_process": "Measured PV string insulation and inspected connectors.",
                "root_cause": "Connector moisture and string insulation degradation.",
                "solution": "Dry or replace abnormal connectors and retest insulation.",
                "tools_used": ["Insulation resistance tester", "Multimeter"],
                "parts_used": ["PV connector kit"],
                "safety_notes": ["Confirm DC and AC isolation", "Wear electrical PPE"],
                "media_ids": [str(demo_media.id)],
                "qa_trace_id": "FINAL-DEMO-QA-LOW-INSULATION",
            },
        )
        converted_doc = ensure_document(
            db,
            "Final Demo Converted SUN2000 Field Contribution Document",
            [
                {
                    "section_title": "SUN2000 low insulation field contribution",
                    "content": converted_contribution.content,
                    "page_number": None,
                }
            ],
            manufacturer="huawei",
            product_series="SUN2000",
            model="SUN2000-50KTL-M3",
            device_type="pv_inverter",
            document_type="maintenance_record",
            source_type="knowledge_contribution",
            file_name=None,
            file_ext=None,
            file_size=None,
            page_count=None,
            parser_name="field_contribution",
            summary="Converted final demo field contribution for Huawei SUN2000 low insulation troubleshooting.",
            status="active",
            submitted_by=admin.id,
            reviewed_by=admin.id,
            reviewed_at=datetime.now(timezone.utc),
        )
        converted_doc.source = f"knowledge_contribution:{converted_contribution.id}"
        converted_doc.metadata_json = {
            "seed_source": DEMO_SOURCE,
            "repeatable": True,
            "source_type": "field_contribution",
            "contribution_id": str(converted_contribution.id),
        }
        converted_contribution.approved_document_id = converted_doc.id
        converted_metadata = dict(converted_contribution.metadata_json or {})
        converted_metadata["converted_document_id"] = str(converted_doc.id)
        converted_contribution.metadata_json = converted_metadata
        ensure_review_record(
            db,
            converted_contribution,
            "approve",
            reviewer_id=admin.id,
            review_comment="Final demo contribution approved.",
            before_status="submitted",
            after_status="approved",
            reviewed_at=datetime.now(timezone.utc),
        )
        ensure_review_record(
            db,
            converted_contribution,
            "convert_to_document",
            document_id=converted_doc.id,
            reviewer_id=admin.id,
            review_comment="Final demo contribution converted into knowledge document and chunks.",
            before_status="approved",
            after_status="converted",
            reviewed_at=datetime.now(timezone.utc),
        )

        ensure_contribution(
            db,
            "Final Demo Pending Knowledge Contribution",
            content="Field engineer notes for Sungrow SG MPPT low generation after string connector inspection.",
            contribution_type="maintenance_experience",
            manufacturer="sungrow",
            product_series="SG",
            device_type="pv_inverter",
            device_id=sungrow_mppt_device.id,
            source_trace_id="FINAL-DEMO-QA-MPPT-LOW-GENERATION",
            submitted_by=admin.id,
            review_status="submitted",
            review_comment="Pending expert review for final demo.",
            metadata_json={
                "seed_source": DEMO_SOURCE,
                "fault_type": "mppt_abnormal",
                "alarm_code": "MPPT-LOW",
                "symptom_description": "Sungrow SG MPPT generation is lower than adjacent inputs.",
                "diagnosis_process": "Compared string current, irradiance, connector condition, and generation curve.",
                "root_cause": "Pending expert confirmation.",
                "solution": "Pending expert review.",
                "tools_used": ["Clamp meter", "Thermal imager"],
                "parts_used": [],
                "safety_notes": ["Confirm DC isolation before connector inspection"],
            },
        )
        ensure_correction(
            db,
            "FINAL-DEMO-QA-LOW-INSULATION",
            source_type="qa",
            original_output={"answer": "Replace inverter immediately."},
            corrected_output={"answer": "Inspect PV string insulation and connectors before considering inverter replacement."},
            correction_reason="Field review confirmed the first step should be DC-side insulation troubleshooting.",
            submitted_by=admin.id,
            review_status="pending_review",
            metadata_json={"seed_source": DEMO_SOURCE},
        )

        db.commit()
        print("Final demo data is ready.")
        print("Users: admin, expert, engineer, viewer")
        print("Devices: EM-DEMO-HW-SUN2000-01, EM-DEMO-HW-FUSIONSOLAR-01, EM-DEMO-SG-01, EM-DEMO-SG-MPPT-01")
        print("Knowledge source:", DEMO_SOURCE)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
