from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeReviewRecord, OperationLog


class DevelopmentEngineeringApprovalService:
    actor = "Development Engineering Reviewer"

    def __init__(self, db: Session):
        self.db = db

    def approve(self, document: KnowledgeDocument, *, metrics: dict, reason: str, rule_version: str) -> bool:
        metadata = dict(document.metadata_json or {})
        if metadata.get("engineering_approved_for_pilot") is True:
            return False
        before = document.review_status
        evidence = {
            "document_id": str(document.id), "before_status": before, "after_status": "approved",
            "approval_mode": "development_engineering_auto", "rule_version": rule_version,
            "quality_score": metrics["quality_score"], "language": metadata.get("normalized_language"),
            "source_provenance": metadata.get("source_provenance"),
            "duplicate_ratio": metrics["exact_duplicate_ratio"], "locator_coverage": metrics["locator_coverage"],
            "page_coverage": metrics["page_coverage"], "heading_coverage": metrics["heading_coverage"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(), "automatic": True,
            "expert_verified": False, "human_expert_verified": False, "second_reviewed": False, "reason": reason,
        }
        evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
        evidence["evidence_hash"] = evidence_hash
        # Preserve any prior human approval mode while recording an independent engineering approval.
        if before != "approved":
            document.review_status = "approved"
            metadata["approval_mode"] = "development_engineering_auto"
        metadata.update({"engineering_approved_for_pilot": True,
            "engineering_approval_mode": "development_engineering_auto",
            "approval_actor_type": "codex_engineering_reviewer", "approval_rule_version": rule_version,
            "approval_reason": reason, "approval_evidence_json": evidence, "approved_for_pilot": True,
            "is_default_retrieval_language": True, "is_pilot_eligible": True,
            "expert_verified": False, "human_expert_verified": False, "second_reviewed": False})
        document.metadata_json = metadata
        document.reviewed_at = datetime.now(timezone.utc)
        self.db.add(KnowledgeReviewRecord(document_id=document.id, reviewer_id=None,
            review_action="engineering_approve_for_pilot", review_comment=reason,
            before_status=before, after_status=document.review_status, metadata_json=evidence))
        self.db.add(OperationLog(module="knowledge_review", action="development_engineering_auto_approval",
            target_type="knowledge_document", target_id=str(document.id), operator=self.actor,
            detail=evidence))
        self.db.add(document)
        return True
