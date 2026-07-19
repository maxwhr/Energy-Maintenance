from __future__ import annotations

import json
from collections import Counter

from task25g_r2_common import now_iso, read_json, sha256_value, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.services.knowledge_graph_fact_identity_service import KnowledgeGraphFactIdentityService

    baseline = read_json("active_fact_baseline.json", {})
    if baseline.get("active_fact_count") != 68:
        raise SystemExit("Task 25G-R2 frozen active fact baseline is missing or invalid")
    with SessionLocal() as session:
        facts = KnowledgeGraphFactIdentityService.list_active_facts(session)
    if len(facts) != 68:
        raise RuntimeError(f"expected 68 active facts, found {len(facts)}")
    baseline_ids = {
        item["fact_id"]
        for item in [*(baseline.get("nodes") or []), *(baseline.get("edges") or [])]
    }
    current_ids = {item["fact_id"] for item in facts}
    if current_ids != baseline_ids:
        raise RuntimeError("active graph fact IDs drifted after Task 25G-R2 freeze")
    kind_counts = Counter(item["fact_kind"] for item in facts)
    category_counts = Counter(item["fact_category"] for item in facts)
    payload = {
        "version": "task25g_r2_fact_inventory_v1",
        "generated_at": now_iso(),
        "status": "PASS",
        "fact_count": len(facts),
        "node_count": kind_counts["NODE"],
        "edge_count": kind_counts["EDGE"],
        "category_counts": dict(sorted(category_counts.items())),
        "facts": facts,
    }
    payload["inventory_sha256"] = sha256_value(payload)
    write_json("fact_inventory.json", payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "facts": payload["fact_count"],
                "nodes": payload["node_count"],
                "edges": payload["edge_count"],
                "categories": payload["category_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
