from __future__ import annotations

import argparse
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.development_engineering_approval_service import DevelopmentEngineeringApprovalService
from task25b_r3_dev_common import RULE_VERSION, now_iso, quality_decision, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-engineering-approval", action="store_true")
    parser.add_argument("--chinese-only", action="store_true")
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--no-expert-verification", action="store_true")
    args = parser.parse_args()
    if not all(vars(args).values()):
        raise SystemExit("all four explicit safety flags are required")
    approved, blocked, english = [], [], []
    with SessionLocal() as db:
        service = DevelopmentEngineeringApprovalService(db)
        docs = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.manufacturer == "huawei")))
        for document in docs:
            metadata = document.metadata_json or {}
            if metadata.get("normalized_language") != "zh-CN":
                if metadata.get("normalized_language") == "en":
                    english.append({"document_id": str(document.id), "retained": True, "retrieval": False, "pilot": False})
                continue
            chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id, KnowledgeChunk.status == "active")))
            passed, reasons, metrics = quality_decision(document, chunks)
            if not passed:
                blocked.append({"document_id": str(document.id), "title": document.title, "reasons": reasons, "metrics": metrics}); continue
            written = service.approve(document, metrics=metrics, reason="all Chinese official engineering quality gates passed", rule_version=RULE_VERSION)
            approved.append({"document_id": str(document.id), "title": document.title, "audit_written": written,
                "already_engineering_approved": not written, "quality_score": metrics["quality_score"]})
        db.commit()
    write_json("engineering_approval_result.json", {"generated_at": now_iso(), "approved": approved,
        "automatic": True, "approval_mode": "development_engineering_auto", "expert_verified": False, "second_reviewed": False})
    write_json("engineering_approval_blocked.json", {"generated_at": now_iso(), "blocked": blocked})
    write_json("english_exclusion_result.json", {"generated_at": now_iso(), "english": english,
        "deleted": 0, "default_retrieval_enabled": False, "pilot_enabled": False})
    print({"status": "passed", "approved": len(approved), "blocked": len(blocked), "english_excluded": len(english)})


if __name__ == "__main__": main()
