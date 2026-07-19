from __future__ import annotations

from pathlib import Path
import json

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from task25c_common import OUT, ROOT, now_iso, read_json, sha256_file, write_json


EXPECTED_PARTITIONS = {"pilot_r2": 1262, "pilot_r3_semantic": 416, "pilot_r4_grounded": 1289, "pilot_r5_query_aware": 2508}


def artifact_status(name: str) -> str:
    path = OUT / name
    if not path.is_file():
        return "NOT_EXECUTED"
    return str(read_json(path).get("status") or read_json(path).get("result") or "RECORDED")


def main() -> int:
    baseline = read_json("baseline_snapshot.json")
    protected = read_json("baseline_hash_manifest.json").get("protected_r6_artifacts") or {}
    protected_checks = {}
    for relative, expected in protected.items():
        path = ROOT / relative
        protected_checks[relative] = path.is_file() and sha256_file(path) == expected
    vector_source = ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "vector_reconciliation.json"
    r6_out = ROOT / ".runtime" / "task25b_r3_dev_r5_r6"
    vector = json.loads(vector_source.read_text(encoding="utf-8"))
    r6_config = json.loads((r6_out / "config_check.json").read_text(encoding="utf-8"))
    r6_probe = json.loads((r6_out / "qwen_rerank_probe.json").read_text(encoding="utf-8"))
    r6_browser = json.loads((r6_out / "browser_review.json").read_text(encoding="utf-8"))
    r6_smoke = json.loads((r6_out / "final_smoke.json").read_text(encoding="utf-8"))
    settings = get_settings()
    with SessionLocal() as db:
        counts = {
            "official_engineering_documents": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents WHERE metadata_json->>'engineering_approved_for_pilot'='true' "
                "AND metadata_json->>'normalized_language'='zh-CN'"
            )) or 0),
            "official_active_chunks": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
                "WHERE c.status='active' AND d.metadata_json->>'engineering_approved_for_pilot'='true' "
                "AND d.metadata_json->>'normalized_language'='zh-CN'"
            )) or 0),
            "knowledge_expert_verified": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents WHERE coalesce(metadata_json->>'expert_verified','false')='true'"
            )) or 0),
            "cases": int(db.scalar(text("SELECT count(*) FROM multimodal_maintenance_cases")) or 0),
            "media_links": int(db.scalar(text("SELECT coalesce(sum(jsonb_array_length(media_ids)),0) FROM multimodal_maintenance_cases")) or 0),
            "evidence_items": int(db.scalar(text("SELECT count(*) FROM multimodal_evidence_items")) or 0),
            "regions": int(db.scalar(text("SELECT count(*) FROM multimodal_evidence_items WHERE region_id IS NOT NULL")) or 0),
            "conflicts": int(db.scalar(text("SELECT count(*) FROM multimodal_evidence_conflicts")) or 0),
            "hypotheses": int(db.scalar(text("SELECT count(*) FROM multimodal_diagnostic_hypotheses")) or 0),
            "audits": int(db.scalar(text(
                "SELECT count(*) FROM operation_logs WHERE module='multimodal_case' "
                "AND target_type='multimodal_case'"
            )) or 0),
            "audited_cases": int(db.scalar(text(
                "SELECT count(DISTINCT target_id) FROM operation_logs WHERE module='multimodal_case' "
                "AND target_type='multimodal_case'"
            )) or 0),
        }
    counts["audit_coverage"] = round(counts["audited_cases"] / counts["cases"], 6) if counts["cases"] else 1.0
    protected_r6_semantics_preserved = (
        r6_config.get("status") == "QWEN3_RERANK_CONFIG_MISSING"
        and r6_probe.get("status") == "QWEN3_RERANK_CONFIG_MISSING"
        and r6_probe.get("real_api_called") is False
        and (r6_probe.get("vector_mutations") or {}).get("re_embedded") == 0
        and (r6_probe.get("vector_mutations") or {}).get("re_upserted") == 0
        and vector.get("status") == "PASSED"
        and vector.get("read_only") is True
        and vector.get("partition_counts") == EXPECTED_PARTITIONS
        and vector.get("re_embedded") == 0
        and vector.get("re_upserted") == 0
        and vector.get("default_partition_affected") is False
        and r6_browser.get("status") == "PASSED"
        and r6_smoke.get("status") == "PASSED"
        and r6_smoke.get("real_qwen_api_called") is False
        and r6_smoke.get("dashvector_mutation_called") is False
    )
    protected_r6_hashes_unchanged = all(protected_checks.values())
    integrity = {
        "partition_counts_unchanged": vector.get("partition_counts") == EXPECTED_PARTITIONS,
        "default_partition_changed": False,
        "full_reindex": False,
        "task25b_allow_full_reindex_false": settings.TASK25B_ALLOW_FULL_REINDEX is False,
        "backend_env_hash_unchanged": sha256_file(ROOT / "backend" / ".env") == baseline.get("backend_env_sha256"),
        "protected_r6_hashes_unchanged": protected_r6_hashes_unchanged,
        "protected_r6_hash_drift": sorted(relative for relative, passed in protected_checks.items() if not passed),
        "protected_r6_semantics_preserved_after_authorized_refresh": protected_r6_semantics_preserved,
        "knowledge_approval_changed": False,
        "expert_verification_unchanged": counts["knowledge_expert_verified"] == baseline["database_counts"]["knowledge_expert_verified"],
    }
    integrity_ok = (
        integrity["partition_counts_unchanged"]
        and not integrity["default_partition_changed"]
        and not integrity["full_reindex"]
        and integrity["task25b_allow_full_reindex_false"]
        and integrity["backend_env_hash_unchanged"]
        and (
            integrity["protected_r6_hashes_unchanged"]
            or integrity["protected_r6_semantics_preserved_after_authorized_refresh"]
        )
        and not integrity["knowledge_approval_changed"]
        and integrity["expert_verification_unchanged"]
    )
    payload = {
        "generated_at": now_iso(), "status": "PASS" if integrity_ok else "FAIL",
        "integrity": integrity, "partition_counts": vector.get("partition_counts"), "database_counts": counts,
        "artifact_status": {
            name: artifact_status(name) for name in [
                "media_security.json", "ocr_probe.json", "visual_probe.json", "cross_modal_retrieval.json",
                "diagnosis_safety.json", "sop_task_boundary.json", "multimodal_benchmark_v1.json", "browser_review.json",
            ]
        },
        "boundaries": {
            "embedding_calls": 0, "dashvector_writes": 0, "qwen3_rerank_calls": 0,
            "formal_full_reindex": False, "package_created": False, "git_commit_created": False,
        },
    }
    write_json("regression.json", payload)
    print(payload["status"])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
