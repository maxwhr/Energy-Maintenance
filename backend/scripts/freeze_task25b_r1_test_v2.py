from __future__ import annotations

import json

from sqlalchemy import select

from task25b_r1_common import now_iso, sha256_file, sha256_text, write_json
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase


DATASET_VERSION = "task25b-r1-v2"


def _logical_split(item: RetrievalEvaluationCase) -> str:
    return str((item.metadata_json or {}).get("logical_split") or item.dataset_split)


def main() -> int:
    with SessionLocal() as db:
        all_cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.source_type == "task25b_r1_engineering_controlled"
        ).order_by(RetrievalEvaluationCase.name)))
        by_split = {
            split: [item for item in all_cases if _logical_split(item) == split]
            for split in ("train", "dev", "test_v2")
        }
        if {name: len(items) for name, items in by_split.items()} != {"train": 72, "dev": 54, "test_v2": 54}:
            raise RuntimeError("R1 split counts do not match the frozen design")

        document_sets = {
            split: {
                str(document_id)
                for item in items
                for document_id in (item.expected_document_ids or [])
            }
            for split, items in by_split.items()
        }
        overlap = {
            "train_dev": sorted(document_sets["train"] & document_sets["dev"]),
            "train_test_v2": sorted(document_sets["train"] & document_sets["test_v2"]),
            "dev_test_v2": sorted(document_sets["dev"] & document_sets["test_v2"]),
        }
        if any(overlap.values()):
            raise RuntimeError("train/dev/test_v2 source document isolation failed")

        labels = []
        for item in by_split["test_v2"]:
            labels.append({
                "case_id": str(item.id),
                "case_name": item.name,
                "category": item.category,
                "query_sha256": sha256_text(item.query_text),
                "expected_document_ids": sorted(str(value) for value in (item.expected_document_ids or [])),
                "expected_chunk_ids": sorted(str(value) for value in (item.expected_chunk_ids or [])),
                "expected_media_ids": sorted(str(value) for value in (item.expected_media_ids or [])),
                "required_filters": item.required_filters or {},
                "difficulty": item.difficulty,
            })
        canonical = json.dumps(labels, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        frozen_hash = sha256_text(canonical)
        for item in by_split["test_v2"]:
            item.metadata_json = {
                **(item.metadata_json or {}),
                "logical_split": "test_v2",
                "labels_frozen": True,
                "frozen_labels_sha256": frozen_hash,
                "blind_runs_allowed": 1,
                "blind_runs_completed": int((item.metadata_json or {}).get("blind_runs_completed") or 0),
            }
            db.add(item)
        db.commit()

    labels_path = write_json("test_v2_labels_frozen.json", {
        "status": "FROZEN", "dataset_version": DATASET_VERSION, "frozen_at": now_iso(),
        "tuning_use_allowed": False, "formal_blind_runs_allowed": 1,
        "labels_sha256": frozen_hash, "case_count": len(labels), "labels": labels,
    })
    manifest = {
        "status": "FROZEN", "dataset_version": DATASET_VERSION, "frozen_at": now_iso(),
        "split_counts": {name: len(items) for name, items in by_split.items()},
        "source_document_overlap": overlap, "source_document_isolation": not any(overlap.values()),
        "test_v2_case_count": len(labels), "test_v2_frozen_hash": frozen_hash,
        "frozen_labels_artifact_sha256": sha256_file(labels_path),
        "tuning_process_must_not_read_test_v2": True, "formal_blind_runs_allowed": 1,
        "formal_blind_runs_completed": 0,
    }
    write_json("test_v2_frozen_manifest.json", manifest)
    print(json.dumps({
        "status": "FROZEN", "test_v2_case_count": len(labels), "test_v2_frozen_hash": frozen_hash,
        "source_document_isolation": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
