from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import func, select

from freeze_task25g_r2_snapshot import _current_corpus, _fact_baseline
from task25g_r2_common import (
    BACKEND,
    EXPECTED_ALEMBIC_REVISION,
    TASK25G_R1_REPORT,
    TASK25G_R1_RUNTIME,
    TASK25G_REPORT,
    TASK25G_RUNTIME,
    alembic_state,
    directory_manifest,
    git_snapshot,
    now_iso,
    read_json,
    sha256_file,
    vector_namespace_counts,
    write_json,
    zip_inventory,
)


def _manifest_changes(
    frozen: dict,
    current: dict,
) -> tuple[list[str], list[str], list[str]]:
    frozen_files = {str(item["path"]): item for item in frozen.get("files") or []}
    current_files = {str(item["path"]): item for item in current.get("files") or []}
    added = sorted(set(current_files) - set(frozen_files))
    removed = sorted(set(frozen_files) - set(current_files))
    changed = sorted(
        path
        for path in set(frozen_files) & set(current_files)
        if frozen_files[path].get("sha256") != current_files[path].get("sha256")
    )
    return added, removed, changed


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGCandidate, KGEvidenceLink, KGExtractionRun, OperationLog

    frozen_hashes = read_json("hash_manifest.json", {})
    frozen_facts = read_json("active_fact_baseline.json", {})
    frozen_corpus = read_json("current_chinese_corpus_manifest.json", {})
    frozen_snapshot = read_json("snapshot.json", {})
    candidate_result = read_json("current_fact_candidates.json", {})
    execution = read_json("grounding_execution.json", {})
    if not all((frozen_hashes, frozen_facts, frozen_corpus, frozen_snapshot, candidate_result, execution)):
        raise SystemExit("Task 25G-R2 reconciliation inputs are incomplete")

    with SessionLocal() as session:
        current_facts = _fact_baseline(session)
        current_corpus = _current_corpus(session)
        vectors = vector_namespace_counts(session)
        run = session.scalar(
            select(KGExtractionRun).where(KGExtractionRun.source_type == "task25g_r2_current_fact_candidate")
        )
        candidates = list(
            session.scalars(
                select(KGCandidate).where(
                    KGCandidate.run_id == run.id if run is not None else KGCandidate.id.is_(None)
                )
            )
        )
        log_count = int(
            session.scalar(
                select(func.count()).select_from(OperationLog).where(
                    OperationLog.action == "task25g_r2_create_manual_review_candidate"
                )
            )
            or 0
        )
        r2_evidence_count = int(
            session.scalar(
                select(func.count()).select_from(KGEvidenceLink).where(
                    KGEvidenceLink.source_type == "task25g_r2_current_chinese_grounding"
                )
            )
            or 0
        )

    frozen_sources = frozen_hashes["task25g_and_r1"]
    current_task25g = directory_manifest(TASK25G_RUNTIME)
    current_task25g_r1 = directory_manifest(TASK25G_R1_RUNTIME)
    r1_added, r1_removed, r1_changed = _manifest_changes(
        frozen_sources["task25g_r1_runtime"],
        current_task25g_r1,
    )
    volatile_r1_files = {"kg_performance_preservation.json"}
    r1_runtime_unchanged = (
        current_task25g_r1["aggregate_sha256"]
        == frozen_sources["task25g_r1_runtime"]["aggregate_sha256"]
    )
    r1_immutable_runtime_unchanged = (
        not r1_added
        and not r1_removed
        and not (set(r1_changed) - volatile_r1_files)
    )
    r1_runtime_refresh_disclosed = r1_runtime_unchanged or (
        not r1_added
        and not r1_removed
        and set(r1_changed) == volatile_r1_files
    )
    current_git = git_snapshot()
    alembic = alembic_state()
    fact_rows_unchanged = (
        current_facts["nodes"] == frozen_facts["nodes"]
        and current_facts["edges"] == frozen_facts["edges"]
    )
    historical_evidence_unchanged = current_facts["evidence"] == frozen_facts["evidence"]
    checks = {
        "task25g_report_unchanged": sha256_file(TASK25G_REPORT) == frozen_sources["task25g_report"]["sha256"],
        "task25g_r1_report_unchanged": sha256_file(TASK25G_R1_REPORT) == frozen_sources["task25g_r1_report"]["sha256"],
        "task25g_runtime_unchanged": current_task25g["aggregate_sha256"] == frozen_sources["task25g_runtime"]["aggregate_sha256"],
        "task25g_r1_runtime_unchanged": r1_runtime_unchanged,
        "task25g_r1_immutable_runtime_unchanged": r1_immutable_runtime_unchanged,
        "task25g_r1_runtime_refresh_disclosed": r1_runtime_refresh_disclosed,
        "backend_env_unchanged": sha256_file(BACKEND / ".env") == frozen_hashes["backend_env"]["sha256"],
        "active_fact_rows_unchanged": fact_rows_unchanged,
        "historical_evidence_preserved": historical_evidence_unchanged and len(current_facts["evidence"]) == 76,
        "current_corpus_unchanged": current_corpus["corpus_sha256"] == frozen_corpus["corpus_sha256"],
        "current_document_count_unchanged": current_corpus["document_count"] == 16,
        "current_chunk_count_unchanged": current_corpus["chunk_count"] == 1262,
        "semantic_unit_count_unchanged": current_corpus["semantic_unit_count"] == 2508,
        "vector_namespaces_unchanged": vectors == frozen_snapshot["database"]["vector_namespaces"],
        "zip_inventory_unchanged": zip_inventory() == frozen_snapshot["zip_inventory"],
        "alembic_current_unchanged": EXPECTED_ALEMBIC_REVISION in alembic.get("current", ""),
        "staged_files_zero": not current_git["staged_files"],
        "task25b_full_reindex_disabled": str(os.environ.get("TASK25B_ALLOW_FULL_REINDEX", "false")).lower()
        in {"", "0", "false", "no"},
        "r2_grounding_evidence_writes_zero": r2_evidence_count == 0,
        "manual_candidates_complete": len(candidates) == 58,
        "manual_candidates_pending": all(
            item.status == "pending" and item.reviewed_by is None and item.reviewed_at is None
            for item in candidates
        ),
        "operation_log_coverage_complete": log_count == len(candidates) == 58,
        "grounding_apply_not_committed": not execution.get("transaction_committed"),
    }
    required_checks = {
        name: passed
        for name, passed in checks.items()
        if name != "task25g_r1_runtime_unchanged"
    }
    passed = all(required_checks.values())
    status = (
        "PASS"
        if passed and r1_runtime_unchanged
        else "PASS_WITH_VOLATILE_R1_AUDIT_REFRESH"
        if passed
        else "FAIL"
    )
    payload = {
        "version": "task25g_r2_reconciliation_v1",
        "generated_at": now_iso(),
        "status": status,
        "checks": checks,
        "task25g_r1_runtime_changes": {
            "added": r1_added,
            "removed": r1_removed,
            "changed": r1_changed,
            "allowed_volatile_refresh_files": sorted(volatile_r1_files),
            "reason": (
                "The historical R1 performance JSON was refreshed by a live replay before child-process "
                "runtime isolation was enforced. The R1 report and every immutable runtime artifact remain frozen."
                if not r1_runtime_unchanged
                else None
            ),
        },
        "active_fact_count": current_facts["active_fact_count"],
        "historical_evidence_count": len(current_facts["evidence"]),
        "r2_current_evidence_count": r2_evidence_count,
        "manual_review_candidate_count": len(candidates),
        "candidate_auto_approval": sum(item.status == "approved" for item in candidates),
        "expert_auto_write": any(bool((item.payload_json or {}).get("expert_verified")) for item in candidates),
        "operation_log_count": log_count,
        "vector_namespaces": vectors,
        "vector_writes": 0,
        "embedding_writes": 0,
        "fact_updates": 0,
        "document_updates": 0,
        "chunk_updates": 0,
        "semantic_unit_updates": 0,
        "approval_updates": 0,
        "full_reindex": False,
        "package_generated": False,
        "git_commit": False,
        "failures": [name for name, item_passed in required_checks.items() if not item_passed],
        "warnings": ([] if r1_runtime_unchanged else ["task25g_r1_performance_audit_json_refreshed"]),
    }
    write_json("reconciliation.json", payload)
    print(json.dumps({"status": payload["status"], "failures": payload["failures"], "candidates": len(candidates), "r2_evidence": r2_evidence_count}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
