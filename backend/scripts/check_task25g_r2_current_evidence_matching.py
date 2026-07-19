from __future__ import annotations

import json
from collections import Counter
from typing import Any

from task25g_r2_common import now_iso, read_json, sha256_value, write_csv, write_json


CSV_FIELDS = [
    "fact_id",
    "fact_kind",
    "fact_category",
    "candidate_id",
    "support_level",
    "document_id",
    "chunk_id",
    "semantic_unit_id",
    "semantic_unit_type",
    "subject_match",
    "object_match",
    "relation_match",
    "scope_valid",
    "locator_valid",
    "conflict",
    "automatic_binding_eligible",
    "review_required",
    "reason",
]


def _fact_summary(item: dict[str, Any]) -> dict[str, Any]:
    fact = item["fact"]
    candidates = item["candidates"]
    best = candidates[0] if candidates else None
    return {
        "fact_id": fact["fact_id"],
        "fact_kind": fact["fact_kind"],
        "fact_category": fact["fact_category"],
        "candidate_count": len(candidates),
        "best_support_level": best["support_level"] if best else "NOT_SUPPORTED",
        "best_document_id": best["document_id"] if best else None,
        "best_chunk_id": best["chunk_id"] if best else None,
        "best_semantic_unit_id": best["semantic_unit_id"] if best else None,
        "best_locator": best["source_locator"] if best else None,
        "subject_match": bool(best and best["subject_match"]),
        "object_match": bool(best and best["object_match"]),
        "relation_match": bool(best and best["relation_match"]),
        "scope_valid": bool(best and best["scope_valid"]),
        "conflict": bool(best and best["conflict"]),
        "automatic_binding_eligible": bool(best and best["automatic_binding_eligible"]),
        "review_required": not bool(best and best["automatic_binding_eligible"]),
        "reason": best["reason"] if best else "no current Chinese candidate matched the fact",
    }


def main() -> int:
    from app.core.database import SessionLocal
    from app.services.knowledge_graph_fact_identity_service import KnowledgeGraphFactIdentityService
    from app.services.kg_current_chinese_evidence_matcher import KGCurrentChineseEvidenceMatcher

    frozen_corpus = read_json("current_chinese_corpus_manifest.json", {})
    if not frozen_corpus or frozen_corpus.get("semantic_unit_count") != 2508:
        raise SystemExit("Task 25G-R2 current Chinese corpus manifest is missing or invalid")
    with SessionLocal() as session:
        facts = KnowledgeGraphFactIdentityService.list_active_facts(session)
        matcher = KGCurrentChineseEvidenceMatcher(session)
        corpus = matcher.load_current_corpus()
        results = matcher.match_facts(facts)
    if len(facts) != 68 or len(results) != 68:
        raise RuntimeError(f"fact matching coverage is incomplete: {len(facts)}/{len(results)}")
    frozen_unit_ids = {item["semantic_unit_id"] for item in frozen_corpus.get("semantic_units") or []}
    current_unit_ids = {item.semantic_unit_id for item in corpus}
    if current_unit_ids != frozen_unit_ids:
        raise RuntimeError("current Chinese semantic-unit corpus drifted after freeze")

    summaries = [_fact_summary(item) for item in results]
    support_counts = Counter(item["best_support_level"] for item in summaries)
    direct_levels = {"DIRECT_EXACT_SUPPORT", "DIRECT_MULTI_SOURCE_SUPPORT"}
    direct_items = [item for item in summaries if item["best_support_level"] in direct_levels]
    candidate_rows = [
        {
            "fact_id": result["fact"]["fact_id"],
            "fact_kind": result["fact"]["fact_kind"],
            "fact_category": result["fact"]["fact_category"],
            **candidate,
        }
        for result in results
        for candidate in result["candidates"]
    ]
    inventory = read_json("fact_inventory.json", {})
    if not inventory:
        inventory = {
            "version": "task25g_r2_fact_inventory_v1",
            "generated_at": now_iso(),
            "status": "PASS",
            "fact_count": len(facts),
            "node_count": sum(item["fact_kind"] == "NODE" for item in facts),
            "edge_count": sum(item["fact_kind"] == "EDGE" for item in facts),
            "facts": facts,
        }
        inventory["inventory_sha256"] = sha256_value(inventory)
        write_json("fact_inventory.json", inventory)
    candidates_payload = {
        "version": "task25g_r2_evidence_match_candidates_v1",
        "generated_at": now_iso(),
        "matcher_version": KGCurrentChineseEvidenceMatcher.VERSION,
        "fact_count": len(results),
        "candidate_count": len(candidate_rows),
        "max_candidates_per_fact": KGCurrentChineseEvidenceMatcher.MAX_CANDIDATES_PER_FACT,
        "results": results,
    }
    candidates_payload["candidates_sha256"] = sha256_value(candidates_payload)
    summary_payload = {
        "version": "task25g_r2_evidence_match_summary_v1",
        "generated_at": now_iso(),
        "status": "PASS",
        "fact_count": len(summaries),
        "matched_fact_count": sum(item["candidate_count"] > 0 for item in summaries),
        "support_counts": dict(sorted(support_counts.items())),
        "direct_support_count": len(direct_items),
        "direct_node_count": sum(item["fact_kind"] == "NODE" for item in direct_items),
        "direct_edge_count": sum(item["fact_kind"] == "EDGE" for item in direct_items),
        "review_required_count": sum(item["review_required"] for item in summaries),
        "corpus": {
            "documents": frozen_corpus["document_count"],
            "chunks": frozen_corpus["chunk_count"],
            "semantic_units": frozen_corpus["semantic_unit_count"],
            "corpus_sha256": frozen_corpus["corpus_sha256"],
        },
        "fact_summaries": summaries,
    }
    summary_payload["summary_sha256"] = sha256_value(summary_payload)
    write_json("evidence_match_candidates.json", candidates_payload)
    write_csv("evidence_match_candidates.csv", candidate_rows, CSV_FIELDS)
    write_json("evidence_match_summary.json", summary_payload)
    print(
        json.dumps(
            {
                "status": summary_payload["status"],
                "facts": summary_payload["fact_count"],
                "candidates": candidates_payload["candidate_count"],
                "support_counts": summary_payload["support_counts"],
                "direct_support": summary_payload["direct_support_count"],
                "direct_nodes": summary_payload["direct_node_count"],
                "direct_edges": summary_payload["direct_edge_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
