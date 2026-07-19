from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalDatasetFreeze, RetrievalEvaluationCase, User
from task25b_r3_dev_common import ROOT, now_iso


DATASET = "task25b_r3_dev_r1_zh_v2"
FREEZE_VERSION = "task25b_r3_dev_r1_zh_v2_test_v2"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def main() -> None:
    canary = json.loads((OUT / "canary_result.json").read_text(encoding="utf-8"))
    if not canary.get("passed"):
        raise SystemExit("test_v2 cannot be frozen before canary passes")
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v2",
        ).order_by(RetrievalEvaluationCase.name)))
        if len(cases) != 30:
            raise SystemExit(f"expected 30 test_v2 cases, got {len(cases)}")
        label_payload = [{
            "case_id": str(item.id), "query_text": item.query_text, "category": item.category,
            "expected_document_ids": item.expected_document_ids or [], "expected_chunk_ids": item.expected_chunk_ids or [],
            "required_filters": item.required_filters or {},
        } for item in cases]
        digest = hashlib.sha256(json.dumps(label_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        existing = db.scalar(select(RetrievalDatasetFreeze).where(RetrievalDatasetFreeze.dataset_version == FREEZE_VERSION))
        if existing:
            if existing.dataset_sha256 != digest:
                raise SystemExit("frozen test_v2 hash mismatch")
            freeze = existing
        else:
            admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
            if admin is None:
                raise SystemExit("admin user required to freeze dataset")
            freeze = RetrievalDatasetFreeze(
                dataset_version=FREEZE_VERSION, dataset_type="development_engineering_test_v2",
                dataset_sha256=digest, case_count=len(cases), freeze_status="frozen",
                frozen_by=admin.id, frozen_at=datetime.now(timezone.utc),
                metadata_json={"source_dataset_version": DATASET, "split": "test_v2", "expert_verified": False,
                               "canary_status": canary.get("status")},
            )
            db.add(freeze)
        for case in cases:
            metadata = dict(case.metadata_json or {})
            metadata.update({"test_v2_frozen": True, "test_v2_sha256": digest, "freeze_version": FREEZE_VERSION})
            case.metadata_json = metadata; db.add(case)
        db.commit(); db.refresh(freeze)
        payload = {"generated_at": now_iso(), "dataset_version": DATASET, "freeze_version": FREEZE_VERSION,
                   "test_v2_cases": len(cases), "test_v2_sha256": digest, "freeze_id": str(freeze.id),
                   "freeze_status": freeze.freeze_status, "expert_verified": False}
    (OUT / "test_v2_freeze.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
