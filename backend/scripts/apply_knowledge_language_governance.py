from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, OperationLog
from app.services.knowledge_language_policy_service import KnowledgeLanguagePolicyService
from task25b_r3_dev_common import now_iso, write_json


def main() -> None:
    policy = KnowledgeLanguagePolicyService()
    rows = []
    changed = 0
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.manufacturer == "huawei")))
        for document in documents:
            chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)))
            sample = "\n".join(item.content or "" for item in chunks[:20])
            before = dict(document.metadata_json or {})
            after = policy.policy_metadata(metadata=before, title=document.title, content=sample)
            # Existing human approvals remain human approvals; policy enrichment is not a new approval.
            document.metadata_json = after
            if before != after:
                changed += 1
                db.add(OperationLog(module="knowledge_language_governance", action="language_policy_applied",
                    target_type="knowledge_document", target_id=str(document.id), operator="Development Engineering Reviewer",
                    detail={"before_language": before.get("normalized_language") or before.get("language"),
                            "after_language": after.get("normalized_language"), "automatic": True,
                            "retrieval_enabled": after.get("is_default_retrieval_language"),
                            "pilot_eligible": after.get("is_pilot_eligible")}))
            rows.append({"document_id": str(document.id), "language": after["normalized_language"],
                         "retrieval_enabled": after["is_default_retrieval_language"],
                         "pilot_eligible": after["is_pilot_eligible"], "retained": True})
        db.commit()
    counts = {name: sum(item["language"] == name for item in rows) for name in ("zh-CN", "en", "bilingual", "unknown")}
    write_json("language_governance_result.json", {"generated_at": now_iso(), "total": len(rows), "changed": changed,
        "counts": counts, "english_deleted": 0, "documents": rows})
    print({"status": "passed", "total": len(rows), "changed": changed, "counts": counts})


if __name__ == "__main__": main()
