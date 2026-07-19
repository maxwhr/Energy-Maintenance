from __future__ import annotations

import json
from collections import defaultdict
from urllib.parse import urlparse

from sqlalchemy import select

from task25b_r2_u3_common import now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeDocument


PRIORITY = {"ALARM_REFERENCE": 0, "TROUBLESHOOTING_GUIDE": 1, "FAQ_TROUBLESHOOTING": 2, "MAINTENANCE_GUIDE": 3, "USER_MANUAL": 4, "INSTALLATION_GUIDE": 5}


def main() -> int:
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.manufacturer == "huawei",
            KnowledgeDocument.review_status == "pending_review",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.source_type.in_(["vendor_official", "vendor_official_html"]),
        )))
    documents.sort(key=lambda item: (PRIORITY.get(item.document_type, 99), -(item.chunk_count or 0), item.title))
    batch_groups: dict[str, list[KnowledgeDocument]] = defaultdict(list)
    individual = []
    for document in documents:
        metadata = document.metadata_json or {}
        if metadata.get("quality_status") == "READY_FOR_HUMAN_REVIEW":
            batch_groups[str(metadata.get("product_family") or document.product_series or "unknown")].append(document)
        else:
            individual.append(document)
    batches = []
    batch_number = 1
    for family, items in sorted(batch_groups.items(), key=lambda pair: min(PRIORITY.get(item.document_type, 99) for item in pair[1])):
        for offset in range(0, len(items), 10):
            group = items[offset:offset + 10]
            batches.append({
                "batch": batch_number, "product_family": family, "count": len(group),
                "documents": [
                    {"id": str(item.id), "title": item.title, "document_type": item.document_type,
                     "source_domain": urlparse(item.source or "").hostname, "quality_status": (item.metadata_json or {}).get("quality_status"), "chunks": item.chunk_count}
                    for item in group
                ],
            })
            batch_number += 1
    payload = {
        "generated_at": now_iso(), "status": "AWAITING_HUMAN_DOCUMENT_APPROVAL",
        "review_url": "http://127.0.0.1:8012/review", "pending_documents": len(documents),
        "batch_eligible": sum(item["count"] for item in batches), "batch_size_limit": 10,
        "recommended_batches": batches,
        "individual_legacy_review": [{"id": str(item.id), "title": item.title, "quality_status": (item.metadata_json or {}).get("quality_status")} for item in individual],
        "automatic_approval": False, "pilot_index_executed": False,
    }
    write_json("u3_review_readiness.json", payload)
    print(json.dumps({"status": payload["status"], "review_url": payload["review_url"], "pending_documents": payload["pending_documents"], "recommended_batches": len(batches), "batch_eligible": payload["batch_eligible"], "individual_review": len(individual)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
