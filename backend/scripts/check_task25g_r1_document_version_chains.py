from __future__ import annotations

import json
from dataclasses import asdict
from uuid import UUID

from task25g_r1_common import now_iso, read_json, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KnowledgeDocument
    from app.services.knowledge_document_version_resolution_service import (
        KnowledgeDocumentVersionResolutionService,
    )

    forensics = read_json("archived_evidence_forensics.json", [])
    document_ids = sorted({UUID(item["source_document_id"]) for item in forensics if item.get("source_document_id")}, key=str)
    items = []
    with SessionLocal() as session:
        service = KnowledgeDocumentVersionResolutionService(session)
        for document_id in document_ids:
            document = session.get(KnowledgeDocument, document_id)
            if not document:
                items.append({"archived_document_id": str(document_id), "resolution_status": "DOCUMENT_MISSING"})
                continue
            result = asdict(service.resolve(document))
            result["archived_document_id"] = str(result["archived_document_id"])
            result["current_successor_document_id"] = (
                str(result["current_successor_document_id"]) if result["current_successor_document_id"] else None
            )
            result["version_chain"] = [str(value) for value in result["version_chain"]]
            items.append(result)
    counts = {}
    for item in items:
        status = item["resolution_status"]
        counts[status] = counts.get(status, 0) + 1
    payload = {
        "version": "task25g_r1_document_version_chains_v1",
        "generated_at": now_iso(),
        "status": "PASS" if items and not any(item["resolution_status"] == "DOCUMENT_MISSING" for item in items) else "FAIL",
        "archived_document_count": len(items),
        "resolution_counts": counts,
        "items": items,
        "title_values_recorded": False,
        "title_similarity_auto_binding_allowed": False,
    }
    write_json("document_version_chains.json", payload)
    print(json.dumps({"status": payload["status"], "resolution_counts": counts}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

