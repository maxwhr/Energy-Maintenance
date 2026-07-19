from __future__ import annotations

import json
from dataclasses import asdict
from uuid import UUID

from task25g_r1_common import now_iso, read_json, sha256_text, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGEvidenceLink, KnowledgeDocument
    from app.services.kg_evidence_equivalence_service import KGEvidenceEquivalenceService

    forensics = read_json("archived_evidence_forensics.json", [])
    chains = read_json("document_version_chains.json", {})
    successors = {
        str(item["archived_document_id"]): item.get("current_successor_document_id")
        for item in chains.get("items") or []
    }
    output = []
    with SessionLocal() as session:
        service = KGEvidenceEquivalenceService(session)
        for item in forensics:
            evidence = session.get(KGEvidenceLink, UUID(item["evidence_id"]))
            if not evidence:
                output.append({"evidence_id": item["evidence_id"], "status": "NOT_FOUND", "reason": "evidence_missing"})
                continue
            successor_id = successors.get(str(item.get("source_document_id")))
            successor = session.get(KnowledgeDocument, UUID(successor_id)) if successor_id else None
            value = asdict(service.evaluate(evidence, successor))
            value["evidence_id"] = str(value["evidence_id"])
            value["successor_document_id"] = str(value["successor_document_id"]) if value["successor_document_id"] else None
            value["supporting_chunk_id"] = str(value["supporting_chunk_id"]) if value["supporting_chunk_id"] else None
            value["supporting_semantic_unit_id"] = (
                str(value["supporting_semantic_unit_id"]) if value["supporting_semantic_unit_id"] else None
            )
            value["matched_term_hashes"] = [sha256_text(term) for term in value.pop("matched_terms")]
            value["missing_term_hashes"] = [sha256_text(term) for term in value.pop("missing_terms")]
            output.append(value)
    counts = {}
    for item in output:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    payload = {
        "version": "task25g_r1_evidence_equivalence_v1",
        "generated_at": now_iso(),
        "status": "PASS" if len(output) == len(forensics) else "FAIL",
        "evidence_count": len(output),
        "equivalence_counts": counts,
        "auto_rebind_count": sum(bool(item.get("auto_rebind_allowed")) for item in output),
        "llm_used": False,
        "items": output,
    }
    write_json("evidence_equivalence.json", payload)
    print(json.dumps({"status": payload["status"], "equivalence_counts": counts}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

