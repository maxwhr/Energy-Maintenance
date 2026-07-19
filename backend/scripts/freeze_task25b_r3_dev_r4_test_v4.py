from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalDatasetFreeze, RetrievalEvaluationCase, User
from task25b_r3_dev_r4_common import OUT, now_iso, read_json, write_json


DATASET = "task25b_r3_dev_r4_zh_v4"
FREEZE = "task25b_r3_dev_r4_zh_v4_test_v4"


def main() -> None:
    canary = read_json(OUT / "canary_iteration_2.json") or read_json(OUT / "canary_iteration_1.json")
    if not canary.get("passed"):
        raise SystemExit("test_v4 freeze blocked: Grounded Canary has not passed")
    manifest = read_json(OUT / "dataset_v4_manifest.json")
    coverage = manifest.get("test_v4") or {}
    thresholds = {"vector_heavy": 25, "model": 10, "alarm": 10, "no_answer": 10, "safety": 8,
                  "communication": 6, "storage": 6, "inverter": 12, "smartlogger": 6}
    failures = [key for key, minimum in thresholds.items() if int(coverage.get(key) or 0) < minimum]
    if failures or manifest.get("canary_overlap") != 0:
        raise SystemExit(f"test_v4 coverage/freshness gate failed: {failures}")
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v4",
        ).order_by(RetrievalEvaluationCase.name)))
        if len(cases) != 60:
            raise SystemExit(f"expected 60 test_v4 cases, got {len(cases)}")
        labels = [{
            "case_id": str(case.id), "query_text": case.query_text, "category": case.category,
            "expected_document_ids": case.expected_document_ids or [], "expected_chunk_ids": case.expected_chunk_ids or [],
            "expected_semantic_unit_ids": (case.metadata_json or {}).get("expected_semantic_unit_ids") or [],
            "metadata": case.metadata_json or {},
        } for case in cases]
        digest = hashlib.sha256(json.dumps(labels, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        freeze = db.scalar(select(RetrievalDatasetFreeze).where(RetrievalDatasetFreeze.dataset_version == FREEZE))
        if freeze and freeze.dataset_sha256 != digest:
            raise SystemExit("frozen test_v4 hash mismatch")
        if freeze is None:
            admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
            if admin is None:
                raise SystemExit("admin actor required")
            freeze = RetrievalDatasetFreeze(
                dataset_version=FREEZE, dataset_type="development_engineering_test_v4",
                dataset_sha256=digest, case_count=60, freeze_status="frozen", frozen_by=admin.id,
                frozen_at=datetime.now(timezone.utc), metadata_json={
                    "source_dataset_version": DATASET, "split": "test_v4", "coverage": coverage,
                    "canary_overlap": 0, "expert_verified": False,
                },
            )
            db.add(freeze)
        for case in cases:
            metadata = dict(case.metadata_json or {})
            metadata.update({"test_v4_frozen": True, "test_v4_sha256": digest, "freeze_version": FREEZE})
            case.metadata_json = metadata
        db.commit(); db.refresh(freeze)
    payload = {"generated_at": now_iso(), "dataset": DATASET, "freeze_version": FREEZE, "cases": 60,
               "sha256": digest, "freeze_id": str(freeze.id), "status": freeze.freeze_status,
               "coverage": coverage, "canary_overlap": 0, "expert_verified": False}
    write_json("test_v4_freeze.json", payload)
    print({"status": "FROZEN", "dataset": DATASET, "cases": 60, "sha256": digest})


if __name__ == "__main__":
    main()
