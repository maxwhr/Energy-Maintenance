from __future__ import annotations

import json

from task25g_r2_common import MATCHER_VERSION, RELATION_MATRIX_VERSION, read_json, write_json


def main() -> int:
    from app.services.task25g_r2_grounding_service import Task25GR2GroundingService

    candidates = read_json("evidence_match_candidates.json", {})
    corpus = read_json("current_chinese_corpus_manifest.json", {})
    if not candidates or not corpus:
        raise SystemExit("Task 25G-R2 matching or corpus evidence is missing")
    manifest = Task25GR2GroundingService.build_manifest(
        results=candidates.get("results") or [],
        corpus_sha256=corpus["corpus_sha256"],
        matcher_version=MATCHER_VERSION,
        relation_matrix_version=RELATION_MATRIX_VERSION,
    )
    existing = read_json("production_core_fact_manifest.json", None)
    if existing is not None:
        if existing.get("manifest_sha256") != manifest["manifest_sha256"]:
            raise SystemExit("frozen Task 25G-R2 production core manifest does not match current evidence")
        manifest = existing
        reused = True
    else:
        write_json("production_core_fact_manifest.json", manifest, overwrite=False)
        reused = False
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "eligible_facts": manifest["gate"]["eligible_fact_count"],
                "nodes": manifest["gate"]["eligible_node_count"],
                "edges": manifest["gate"]["eligible_edge_count"],
                "relation_types": manifest["gate"]["relation_type_count"],
                "reused_frozen_manifest": reused,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

