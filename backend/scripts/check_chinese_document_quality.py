from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from task25b_r3_dev_common import now_iso, quality_decision, write_json


def main() -> None:
    rows = []
    with SessionLocal() as db:
        docs = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.manufacturer == "huawei")))
        for document in docs:
            chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id, KnowledgeChunk.status == "active")))
            passed, reasons, metrics = quality_decision(document, chunks)
            rows.append({"document_id": str(document.id), "title": document.title, "review_status": document.review_status,
                "language": (document.metadata_json or {}).get("normalized_language"), "quality_passed": passed,
                "decision": "ENGINEERING_APPROVAL_ELIGIBLE" if passed else "ENGINEERING_APPROVAL_BLOCKED",
                "reasons": reasons, **metrics})
    write_json("chinese_document_quality.json", {"generated_at": now_iso(), "documents": rows,
        "eligible": sum(item["quality_passed"] for item in rows), "blocked": sum(not item["quality_passed"] for item in rows)})
    print({"status": "passed", "documents": len(rows), "eligible": sum(x["quality_passed"] for x in rows)})


if __name__ == "__main__": main()
