from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalDatasetFreeze, RetrievalEvaluationCase, User
from task25b_r3_dev_r2_common import OUT, V3_DATASET, V3_FREEZE, now_iso


def main() -> None:
    canary_path = OUT / "canary_result.json"
    canary = json.loads(canary_path.read_text(encoding="utf-8")) if canary_path.exists() else {}
    if not canary.get("passed"):
        raise SystemExit("test_v3 cannot be frozen: CANARY_FAILED")
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V3_DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v3",
        ).order_by(RetrievalEvaluationCase.name)))
        if len(cases) != 60:
            raise SystemExit(f"expected 60 test_v3 cases, got {len(cases)}")
        labels = [{"case_id": str(case.id), "query_text": case.query_text, "category": case.category,
                   "expected_document_ids": case.expected_document_ids or [], "expected_chunk_ids": case.expected_chunk_ids or [],
                   "metadata": case.metadata_json or {}} for case in cases]
        digest = hashlib.sha256(json.dumps(labels, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        freeze = db.scalar(select(RetrievalDatasetFreeze).where(RetrievalDatasetFreeze.dataset_version == V3_FREEZE))
        if freeze and freeze.dataset_sha256 != digest:
            raise SystemExit("frozen test_v3 hash mismatch")
        if not freeze:
            admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
            if admin is None:
                raise SystemExit("admin user required")
            freeze = RetrievalDatasetFreeze(dataset_version=V3_FREEZE, dataset_type="development_engineering_test_v3",
                                            dataset_sha256=digest, case_count=60, freeze_status="frozen", frozen_by=admin.id,
                                            frozen_at=datetime.now(timezone.utc), metadata_json={"source_dataset_version": V3_DATASET, "split": "test_v3", "expert_verified": False})
            db.add(freeze)
        for case in cases:
            metadata = dict(case.metadata_json or {}); metadata.update({"test_v3_frozen": True, "test_v3_sha256": digest, "freeze_version": V3_FREEZE})
            case.metadata_json = metadata; db.add(case)
        db.commit(); db.refresh(freeze)
    payload = {"generated_at": now_iso(), "dataset": V3_DATASET, "freeze_version": V3_FREEZE, "cases": 60, "sha256": digest,
               "freeze_id": str(freeze.id), "status": freeze.freeze_status, "expert_verified": False}
    (OUT / "test_v3_freeze.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
