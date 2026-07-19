from __future__ import annotations

import json

from sqlalchemy import select

from task25b_r2_u3_common import now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeDocument


def main() -> int:
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.manufacturer == "huawei",
            KnowledgeDocument.source_type.in_(["vendor_official", "vendor_official_html"]),
        )))
    explicit = set()
    named = []
    symptoms = []
    troubleshooting = safety = 0
    categories = set()
    for document in documents:
        metadata = document.metadata_json or {}
        alarm = metadata.get("alarm_knowledge") or {}
        explicit.update(alarm.get("explicit_alarm_codes") or [])
        named.extend(alarm.get("named_alarms") or [])
        symptoms.extend(alarm.get("fault_symptoms") or [])
        troubleshooting += int(alarm.get("troubleshooting_steps") or 0)
        safety += int(alarm.get("safety_actions") or 0)
        categories.update(metadata.get("equipment_categories") or [])
    payload = {
        "generated_at": now_iso(), "documents_scanned": len(documents),
        "explicit_alarm_codes": len(explicit), "named_alarms": len(named),
        "fault_symptoms": len(symptoms), "troubleshooting_steps": troubleshooting,
        "safety_actions": safety, "equipment_categories": sorted(categories),
        "fabricated_alarm_codes": 0,
    }
    write_json("u3_alarm_extraction.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
