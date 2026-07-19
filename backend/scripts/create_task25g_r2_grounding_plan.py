from __future__ import annotations

import json

from task25g_r2_common import now_iso, read_json, write_csv, write_json


CSV_FIELDS = [
    "operation",
    "fact_id",
    "source_document_id",
    "source_chunk_id",
    "source_semantic_unit_id",
    "source_locator",
    "support_level",
    "old_state_hash",
    "new_state_hash",
    "equivalence_evidence",
    "reversible",
    "requires_explicit_apply",
]


def main() -> int:
    from app.services.task25g_r2_grounding_service import Task25GR2GroundingService

    manifest = read_json("production_core_fact_manifest.json", {})
    inventory = read_json("fact_inventory.json", {})
    snapshot = read_json("snapshot.json", {})
    fact_baseline = read_json("active_fact_baseline.json", {})
    if not manifest or not inventory or not snapshot or not fact_baseline:
        raise SystemExit("Task 25G-R2 manifest, inventory, snapshot, or fact baseline is missing")
    historical_ids = fact_baseline.get("evidence") or []
    plan = Task25GR2GroundingService.build_plan(
        manifest=manifest,
        all_facts=inventory.get("facts") or [],
        historical_evidence_ids=historical_ids,
    )
    plan["generated_at"] = now_iso()
    Task25GR2GroundingService.validate_plan(plan)
    write_json("grounding_plan.json", plan)
    write_csv("grounding_plan.csv", plan["operations"], CSV_FIELDS)
    counts = {}
    for item in plan["operations"]:
        counts[item["operation"]] = counts.get(item["operation"], 0) + 1
    print(json.dumps({"status": plan["status"], "operations": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
