from __future__ import annotations

import json
import os

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from task25b_r3_dev_r5_r5_common import OUT, now_iso, write_once


def main() -> None:
    settings = get_settings()
    if os.getenv("TASK25B_ALLOW_FULL_REINDEX", "false").lower() != "false":
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    if not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("TASK25B_ALLOW_REAL_API=true is required for the read-only probe")
    settings.RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED = False
    settings.RAG_OPTIONAL_LLM_TIEBREAK_ENABLED = False
    dataset = json.loads((OUT / "train_dev_dataset_v1.json").read_text(encoding="utf-8"))
    candidates = [row for row in dataset["rows"] if not row.get("no_answer") and not row.get("requires_clarification")]
    selected = [candidates[index] for index in (0, 8, 16, 24, 32)]
    rows = []
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("no user available for query-aware service")
        service = QueryAwareRetrievalService(db, current_user=user)
        for case in selected:
            response = service.search(QueryAwareSearchRequest(
                query=case["query"], retrieval_mode="auto", top_k=10,
                enable_llm=False, allow_real_api=True,
            )).model_dump(mode="json")
            rows.append({
                "case_id": case["case_id"],
                "primary_intent": response["primary_intent"],
                "requested_information": response["requested_information"],
                "query_variants": response["generated_queries"],
                "anchor_types": (response.get("retrieval_plan") or {}).get("anchor_types") or [],
                "requested_channels": response["requested_channels"],
                "actual_channels": response["actual_channels"],
                "raw_candidate_count": len(response["raw_results"]),
                "surfaced_count": len(response["surfaced_results"]),
                "top_direct_answer_level": (
                    response["surfaced_results"][0].get("direct_answer_level")
                    if response["surfaced_results"] else None
                ),
                "citation_validity_ratio": response["citation_validity_ratio"],
                "confidence_status": response["confidence_status"],
                "stage_latency": response["stage_latency"],
                "failed_channels": response["failed_channels"],
                "minimax_called": bool((response.get("minimax_tiebreak") or {}).get("called")),
            })
    passed = all(
        row["raw_candidate_count"] > 0
        and "RAW_VECTOR" in row["actual_channels"]
        and "SEMANTIC_UNIT" in row["actual_channels"]
        and not row["failed_channels"]
        and not row["minimax_called"]
        for row in rows
    )
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "read_only": True,
        "vector_mutations": {"re_embedded": 0, "re_upserted": 0},
        "cases": len(rows),
        "rows": rows,
    }
    write_once("probe.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
