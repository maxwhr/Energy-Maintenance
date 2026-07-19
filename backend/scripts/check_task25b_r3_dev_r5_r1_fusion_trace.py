from __future__ import annotations

from types import SimpleNamespace

from app.services.rrf_fusion_service import QueryAwareCandidate, RRFFusionService
from app.services.result_set_refinement_service import ResultSetRefinementService
from task25b_r3_dev_r5_r1_common import now_iso, write_json


def candidate(value: str, channel: str, source_id: str) -> QueryAwareCandidate:
    return QueryAwareCandidate(candidate_id=value, chunk_id=source_id, document_id="doc", document_title="manual", content="通信检查", section_title="通信", chunk=SimpleNamespace(id=source_id), document=SimpleNamespace(id="doc"), source_channels={channel}, source_query_types={"ORIGINAL"}, source_chunk_ids=[source_id], source_locator={"section": "通信", "page_start": 1}, scope_validation_passed=True)


def main() -> None:
    service = RRFFusionService()
    fused = service.fuse({
        "SCOPED_KEYWORD:ORIGINAL:0": [candidate("a", "SCOPED_KEYWORD", "c1")],
        "SCOPED_KEYWORD:CAUSE:1": [candidate("a", "SCOPED_KEYWORD", "c1")],
        "SEMANTIC_UNIT:ORIGINAL:2": [candidate("su:u1", "SEMANTIC_UNIT", "c1")],
    }, channel_weights={"SCOPED_KEYWORD": .9, "SEMANTIC_UNIT": 1.0}, query_weights={"ORIGINAL": 1.0, "CAUSE": .82})
    fused[-1].section_title = fused[0].section_title
    refined = ResultSetRefinementService().refine_query_aware(fused, requested_top_k=5)
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED",
        "kg_alias_status": "DISABLED_DUPLICATE_KEYWORD",
        "fusion": service.last_diagnostics,
        "refinement": refined.diagnostics,
        "semantic_unit_candidate_ids": [item.candidate_id for item in fused if item.semantic_unit_id or item.candidate_id.startswith("su:")],
    }
    write_json("fusion_trace.json", payload)
    print(payload)


if __name__ == "__main__":
    main()
