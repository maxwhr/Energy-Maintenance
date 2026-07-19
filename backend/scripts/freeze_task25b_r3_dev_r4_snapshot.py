from __future__ import annotations

import csv
import subprocess

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import MaintenanceSemanticAnchor, RetrievalEvaluationCase
from task25b_r3_dev_r4_common import OUT, R3_OUT, now_iso, read_json, sha256_file, sha256_text, write_json


R3_FILES = (
    "r2_snapshot.json", "r2_hash_manifest.json", "vector_heavy_grounding.json",
    "embedding_pair_diagnostics.json", "dashvector_recall_trace.json",
    "semantic_anchor_index.json", "semantic_reconciliation.json", "canary_result.json",
)


def main() -> None:
    if any((OUT / name).exists() for name in ("r3_snapshot.json", "r3_hash_manifest.json", "r3_failed_cases.csv")):
        raise SystemExit("R4 snapshot already exists; refusing to overwrite frozen artifacts")
    r3 = read_json(R3_OUT / "canary_result.json")
    grounding = read_json(R3_OUT / "vector_heavy_grounding.json")
    with SessionLocal() as db:
        r3_anchors = int(db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == "pilot_r3_semantic",
            MaintenanceSemanticAnchor.index_status == "active",
        )) or 0)
        r3_dataset_cases = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == "task25b_r3_dev_r3_grounded_train_dev_v1"
        )) or 0)
    git_status = subprocess.run(
        ["git", "status", "--short"], cwd=OUT.parents[1], capture_output=True, text=True, check=False,
    ).stdout
    snapshot = {
        "generated_at": now_iso(), "read_only": True, "history_mutated": False,
        "r2_canary": read_json(R3_OUT / "r2_snapshot.json").get("r2_canary_status"),
        "r3_canary": r3.get("status"), "r3_candidate_recall_at_50": (r3.get("vector_heavy") or {}).get("candidate_recall_at_50"),
        "r3_grounding": grounding.get("summary"), "r3_grounding_cases": grounding.get("cases_reviewed"),
        "r3_embedding_diagnosis": read_json(R3_OUT / "embedding_pair_diagnostics.json").get("primary_diagnosis"),
        "r3_raw_dashvector": {key: read_json(R3_OUT / "dashvector_recall_trace.json").get(key) for key in ("raw_top50_hit", "post_filter_hit", "mapping_failures", "filter_drops")},
        "pilot_r2": read_json(R3_OUT / "r2_snapshot.json").get("pilot_r2_reconciliation"),
        "pilot_r3_semantic": {"active_anchors": r3_anchors, "reconciliation": read_json(R3_OUT / "semantic_reconciliation.json")},
        "r3_dataset_cases": r3_dataset_cases, "alembic_current": "20260712_0012",
        "backend_env_sha256": sha256_file(OUT.parents[1] / "backend" / ".env"),
        "git_status_sha256": sha256_text(git_status), "git_status_entry_count": len([line for line in git_status.splitlines() if line.strip()]),
        "test_v4_created": False, "formal_run_count": 0, "expert_verified": False,
    }
    write_json("r3_snapshot.json", snapshot)
    manifest = {
        "generated_at": now_iso(), "algorithm": "sha256", "read_only": True,
        "r3_artifacts": {name: sha256_file(R3_OUT / name) for name in R3_FILES},
        "snapshot_artifacts": {"r3_snapshot.json": sha256_file(OUT / "r3_snapshot.json")},
    }
    write_json("r3_hash_manifest.json", manifest)
    rows = [row for row in (r3.get("rows") or []) if row.get("vector_heavy") and not row.get("candidate_hit_at_50")]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "r3_failed_cases.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("case_id", "mode", "candidate_hit_at_50", "recall_at_5", "actual_route", "fallback_used", "error"))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})
    print({"status": "FROZEN", "r2": snapshot["r2_canary"], "r3": snapshot["r3_canary"], "failed_rows": len(rows)})


if __name__ == "__main__":
    main()
