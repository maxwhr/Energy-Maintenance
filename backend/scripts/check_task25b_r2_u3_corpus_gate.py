from __future__ import annotations

import argparse
import json
from collections import Counter

from sqlalchemy import select

from task25b_r2_u3_common import now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeDocument


OFFICIAL_PROVENANCE = {"VENDOR_OFFICIAL", "COMPETITION_PROVIDED", "ENTERPRISE_INTERNAL", "TEAM_AUTHORED_REAL_CASE", "PUBLIC_STANDARD"}


def is_official(document: KnowledgeDocument) -> bool:
    metadata = document.metadata_json or {}
    return bool(metadata.get("official_source") or metadata.get("source_provenance") in OFFICIAL_PROVENANCE)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-after-document-approval", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.manufacturer == "huawei")))
    candidates = [item for item in documents if is_official(item) and item.parse_status == "parsed" and item.status == "active"]
    approved = [item for item in candidates if item.review_status == "approved" and bool((item.metadata_json or {}).get("approved_for_pilot"))]
    pending = [item for item in candidates if item.review_status == "pending_review"]
    projected_chunks = sum(item.chunk_count for item in candidates if not (item.metadata_json or {}).get("marketing_only") and not (item.metadata_json or {}).get("duplicate"))
    active_chunks = sum(item.chunk_count for item in approved)
    categories = Counter(category for item in approved for category in ((item.metadata_json or {}).get("equipment_categories") or []))
    document_types = {item.document_type for item in approved}
    explicit = {code for item in approved for code in (((item.metadata_json or {}).get("alarm_knowledge") or {}).get("explicit_alarm_codes") or [])}
    named = sum(len((((item.metadata_json or {}).get("alarm_knowledge") or {}).get("named_alarms") or [])) for item in approved)
    symptoms = sum(len((((item.metadata_json or {}).get("alarm_knowledge") or {}).get("fault_symptoms") or [])) for item in approved)
    troubleshooting = sum(int(((item.metadata_json or {}).get("alarm_knowledge") or {}).get("troubleshooting_steps") or 0) for item in approved)
    safety = sum(int(((item.metadata_json or {}).get("alarm_knowledge") or {}).get("safety_actions") or (item.metadata_json or {}).get("safety_section_count") or 0) for item in approved)
    failures = []
    checks = {
        "approved_official_documents": (len(approved), 15),
        "active_formal_chunks": (active_chunks, 300),
        "inverter_documents": (sum("pv_inverter" in ((item.metadata_json or {}).get("equipment_categories") or []) for item in approved), 5),
        "storage_documents": (sum("energy_storage" in ((item.metadata_json or {}).get("equipment_categories") or []) for item in approved), 2),
        "smartguard_management_communication_documents": (sum(bool(set((item.metadata_json or {}).get("equipment_categories") or []) & {"smart_guard", "management_platform", "communication_device", "data_logger", "plant_controller"}) for item in approved), 2),
        "document_types": (len(document_types), 5),
        "alarm_knowledge": (len(explicit) + named, 20),
        "troubleshooting_sections": (troubleshooting, 30),
        "safety_sections": (safety, 20),
    }
    for name, (actual, required) in checks.items():
        if actual < required:
            failures.append({"gate": name, "actual": actual, "required": required, "gap": required - actual})
    unknown = sum((item.metadata_json or {}).get("source_provenance") not in OFFICIAL_PROVENANCE for item in approved)
    marketing_leakage = sum(bool((item.metadata_json or {}).get("marketing_only")) for item in approved)
    duplicate_leakage = sum(bool((item.metadata_json or {}).get("duplicate")) for item in approved)
    pending_leakage = 0
    for name, value in (("unknown_provenance", unknown), ("marketing_leakage", marketing_leakage), ("pending_leakage", pending_leakage), ("duplicate_leakage", duplicate_leakage)):
        if value:
            failures.append({"gate": name, "actual": value, "required": 0, "gap": value})
    if not failures:
        status = "CORPUS_READY"
    elif 250 <= active_chunks <= 299:
        status = "NEAR_READY"
    else:
        status = "CORPUS_BLOCKED"
    payload = {
        "generated_at": now_iso(), "status": status,
        "resume_requested": args.resume_after_document_approval,
        "approved_official_documents": len(approved), "approved_huawei_documents": len(approved),
        "active_formal_chunks": active_chunks, "projected_chunks_after_approval": projected_chunks,
        "pending_official_documents": len(pending), "equipment_categories": dict(categories),
        "document_types": sorted(document_types), "explicit_alarm_codes": len(explicit), "named_alarms": named,
        "fault_symptoms": symptoms, "troubleshooting_sections": troubleshooting, "safety_sections": safety,
        "unknown_provenance": unknown, "marketing_leakage": marketing_leakage,
        "pending_leakage": pending_leakage, "duplicate_leakage": duplicate_leakage,
        "failures": failures, "pilot_index_allowed": status == "CORPUS_READY",
    }
    write_json("u3_corpus_gate.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if status == "CORPUS_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
