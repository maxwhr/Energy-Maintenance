from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.document_parser import ParsedDocument, ParsedPage
from app.services.text_splitter import TextSplitter


DEMO_DOCUMENTS = [
    {
        "title": "Huawei SUN2000 low insulation resistance troubleshooting",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "document_type": "alarm_code",
        "text": """
Low insulation resistance alarm on Huawei SUN2000 PV inverter.

Safety confirmation:
Isolate AC and DC sides according to the manufacturer safety manual before field inspection.
Use insulated tools and confirm the absence of voltage before touching cable terminals.

Troubleshooting steps:
Check PV string insulation resistance and compare it with site acceptance values.
Inspect DC connectors for moisture, loose terminals, damaged cable insulation, or polluted junction boxes.
Check whether recent rain, high humidity, or module cleaning caused temporary insulation decline.
After correcting the abnormal string, reset the alarm and verify inverter operation in FusionSolar.
""",
    },
    {
        "title": "Huawei FusionSolar communication interruption troubleshooting",
        "manufacturer": "huawei",
        "product_series": "FusionSolar",
        "document_type": "sop",
        "text": """
FusionSolar communication interruption handling.

Confirm whether the SUN2000 inverter is online locally and whether the datalogger has power.
Check RS485 polarity, shielding, terminal resistance, and communication address configuration.
Check Ethernet or 4G network status when remote monitoring is offline.
After restoring communication, compare the local inverter status with FusionSolar alarms and record the recovery time.
""",
    },
    {
        "title": "Sungrow SG overtemperature handling",
        "manufacturer": "sungrow",
        "product_series": "SG",
        "document_type": "fault_case",
        "text": """
Sungrow SG series PV inverter overtemperature and derating case.

Safety notes:
Do not open high-voltage compartments until shutdown and discharge requirements are met.
Keep the work area ventilated and avoid blocking heat dissipation paths.

Inspection:
Check ambient temperature, cooling fan operation, air inlet filter cleanliness, and heat sink dust accumulation.
Confirm whether the inverter is exposed to direct sunlight or installed with insufficient clearance.
Clean ventilation paths, replace abnormal fans, restart the unit, and monitor whether derating disappears.
""",
    },
    {
        "title": "Sungrow SG MPPT low power troubleshooting",
        "manufacturer": "sungrow",
        "product_series": "SG",
        "document_type": "inspection_standard",
        "text": """
Sungrow SG MPPT low power generation inspection.

Compare string current and voltage among MPPT channels under similar irradiance.
Inspect PV module shading, broken connectors, string fuse status, and DC cable polarity.
Check whether the alarm record contains MPPT abnormal, DC abnormal, or device offline events.
After field correction, confirm generation recovery and archive the inspection result.
""",
    },
]


def seed_demo_knowledge() -> None:
    db = SessionLocal()
    splitter = TextSplitter(chunk_size=800, overlap=120)
    repository = KnowledgeRepository(db)
    inserted = 0
    try:
        for item in DEMO_DOCUMENTS:
            if repository.get_document_by_title(item["title"]):
                continue
            document = KnowledgeDocument(
                title=item["title"],
                manufacturer=item["manufacturer"],
                product_series=item["product_series"],
                device_type="pv_inverter",
                document_type=item["document_type"],
                source="demo_seed",
                source_type="seed",
                parse_status="parsed",
                parser_name="seed_text",
                summary=item["text"].strip().splitlines()[0],
                review_status="pending_review",
                status="active",
                parsed_at=datetime.now(timezone.utc),
                metadata_json={"seed": True},
            )
            document = repository.create_document(document)
            parsed = ParsedDocument(
                text=item["text"],
                pages=[ParsedPage(page_number=None, text=item["text"])],
                metadata={"parser": "seed_text"},
            )
            chunks = splitter.split(parsed)
            chunk_models = [
                KnowledgeChunk(
                    document_id=document.id,
                    manufacturer=document.manufacturer,
                    product_series=document.product_series,
                    device_type=document.device_type,
                    document_type=document.document_type,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    section_title=chunk.section_title,
                    char_count=chunk.char_count,
                    page_number=chunk.page_number,
                    embedding_status="pending",
                    metadata_json=chunk.metadata,
                    status="active",
                )
                for chunk in chunks
            ]
            repository.create_chunks(chunk_models)
            document.chunk_count = len(chunk_models)
            repository.update_document(document)
            inserted += 1
        db.commit()
        print(f"Demo knowledge seeding completed. inserted={inserted}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_knowledge()
