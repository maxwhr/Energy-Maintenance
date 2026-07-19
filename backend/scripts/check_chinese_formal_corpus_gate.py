from __future__ import annotations

from collections import Counter
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument
from task25b_r3_dev_common import chunk_quality, now_iso, write_json


def main() -> None:
    with SessionLocal() as db:
        all_docs = list(db.scalars(select(KnowledgeDocument)))
        eligible_docs = []
        metrics_by_doc = {}
        eligible_chunks = []
        for document in all_docs:
            metadata = document.metadata_json or {}
            if not (document.manufacturer == "huawei" and document.review_status == "approved"
                    and metadata.get("normalized_language") == "zh-CN"
                    and metadata.get("engineering_approved_for_pilot") is True
                    and metadata.get("approved_for_pilot") is True
                    and not metadata.get("marketing_only") and not metadata.get("superseded")
                    and metadata.get("source_provenance") in {"VENDOR_OFFICIAL", "VENDOR_OFFICIAL_ZH"}):
                continue
            chunks = list(db.scalars(select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document.id, KnowledgeChunk.status == "active")))
            chunks = [c for c in chunks if document.document_type == "FAQ_TROUBLESHOOTING" or (c.metadata_json or {}).get("current_chunk_version") is True]
            if not chunks: continue
            eligible_docs.append(document); eligible_chunks.extend(chunks)
            metrics_by_doc[str(document.id)] = chunk_quality(document, chunks)
        types = Counter(doc.document_type for doc in eligible_docs)
        categories = Counter(cat for doc in eligible_docs for cat in (doc.metadata_json or {}).get("equipment_categories", []))
        alarm = sum(item["alarm_identifiers"] for item in metrics_by_doc.values())
        trouble = sum(item["troubleshooting_sections"] for item in metrics_by_doc.values())
        safety = sum(item["safety_sections"] for item in metrics_by_doc.values())
        exact = sum(item["exact_duplicate_count"] for item in metrics_by_doc.values())
        vector_rows = list(db.scalars(select(KnowledgeChunkVectorIndex).where(
            KnowledgeChunkVectorIndex.namespace == "pilot_r2", KnowledgeChunkVectorIndex.index_status == "active")))
        vector_doc_ids = {item.document_id for item in vector_rows}
        vector_docs = [doc for doc in all_docs if doc.id in vector_doc_ids]
        leakage = {
            "english": sum((doc.metadata_json or {}).get("normalized_language") == "en" for doc in vector_docs),
            "pending": sum(doc.review_status != "approved" for doc in vector_docs),
            "marketing": sum(bool((doc.metadata_json or {}).get("marketing_only")) for doc in vector_docs),
            "duplicate": exact,
        }
        requirements = {
            "approved_documents_gte_15": len(eligible_docs) >= 15,
            "active_current_chunks_gte_300": len(eligible_chunks) >= 300,
            "document_types_gte_5": len(types) >= 5,
            "inverter_documents_gte_5": categories["pv_inverter"] >= 5,
            "storage_documents_gte_2": categories["energy_storage"] >= 2,
            "communication_management_gte_2": categories["communication_device"] + categories["management_platform"] >= 2,
            "alarm_identifiers_gte_20": alarm >= 20,
            "troubleshooting_sections_gte_30": trouble >= 30,
            "safety_sections_gte_20": safety >= 20,
            "unknown_provenance_zero": all((doc.metadata_json or {}).get("source_provenance") in {"VENDOR_OFFICIAL", "VENDOR_OFFICIAL_ZH"} for doc in eligible_docs),
            "english_pilot_leakage_zero": leakage["english"] == 0,
            "marketing_leakage_zero": leakage["marketing"] == 0,
            "pending_leakage_zero": leakage["pending"] == 0,
            "duplicate_leakage_zero": leakage["duplicate"] == 0,
        }
        passed = all(requirements.values())
        status = "CHINESE_CORPUS_GATE_PASSED" if passed else "CHINESE_CORPUS_INSUFFICIENT"
        payload = {"generated_at": now_iso(), "status": status, "passed": passed,
            "approved_documents": len(eligible_docs), "active_current_chunks": len(eligible_chunks),
            "document_types": dict(types), "equipment_categories": dict(categories),
            "alarm_identifiers": alarm, "troubleshooting_sections": trouble, "safety_sections": safety,
            "exact_duplicates": exact, "vector_leakage": leakage, "requirements": requirements,
            "document_ids": [str(doc.id) for doc in eligible_docs]}
        write_json("chinese_corpus_gate.json", payload)
        print({"status": status, "passed": passed, "documents": len(eligible_docs), "chunks": len(eligible_chunks), "failed_requirements": [k for k,v in requirements.items() if not v]})


if __name__ == "__main__": main()
